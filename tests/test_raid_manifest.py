"""End-to-end synthetic preparation and tamper rejection; no external data."""

import csv
import dataclasses
import json
import subprocess
import sys

import pytest
from test_raid_preparation import StubTokenizer, population

from litmus.data_prep import pipeline
from litmus.data_prep.acquisition import Budget, PrepError, file_hash
from litmus.data_prep.manifest import load_jsonl, validate_manifest
from litmus.data_prep.schema import COLUMNS, index_metadata
from litmus.data_prep.verification import compare_runs, verify


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "source_identity",
        lambda root: {
            "unit": "synthetic",
            "src/litmus/data_prep/acquisition.py": "historical",
        },
    )
    raw = tmp_path / "synthetic.csv"
    with raw.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, COLUMNS)
        writer.writeheader()
        for item in population(8):
            value = dataclasses.asdict(item)
            value.update(title="", prompt="", generation=(item.id + " content ") * 20)
            writer.writerow(value)
    options = {
        "raw": raw,
        "target": 6,
        "expected_sha": file_hash(raw),
        "expected_size": raw.stat().st_size,
    }
    tokenizer = StubTokenizer()
    identity = {"unit_test_tokenizer": True}
    pipeline.prepare(tmp_path, "unit1", tokenizer, identity, **options)
    return tmp_path, raw, tokenizer, identity, options


def test_full_synthetic_repeat_and_verification(prepared):
    root, raw, tokenizer, identity, options = prepared
    result = verify(root, "unit1", tokenizer, identity, raw=raw)
    assert result["status"] == "PASS"
    assert result["selected_texts_recomputed"] == 12
    pipeline.prepare(root, "unit2", tokenizer, identity, **options)
    assert compare_runs(root, "unit1", "unit2")["status"] == "PASS"
    output = root / "eval/manifests/r1e/unit1"
    manifest, _, rows = validate_manifest(output)
    assert manifest["payload"]["scoring_performed"] is False
    assert len(rows) == 12
    counts = json.loads((output / "counts.json").read_text())
    assert counts["candidate_rows"] == counts["retained_rows"] == 12
    assert counts["future_5pct_calibration_count_eligible"] is False


@pytest.mark.parametrize("change", ["text", "ledger", "manifest", "tokenizer", "raw"])
def test_tampering_is_rejected(prepared, change):
    root, raw, tokenizer, identity, _ = prepared
    output = root / "eval/manifests/r1e/unit1"
    if change == "text":
        row = load_jsonl(output / "retained.jsonl")[0]
        (root / "data/raid/prepared/unit1" / row["text_blob"]).write_text("changed")
    elif change == "ledger":
        with (output / "retained.jsonl").open("ab") as stream:
            stream.write(b"{}\n")
    elif change == "manifest":
        path = output / "manifest.json"
        value = json.loads(path.read_text())
        value["payload"]["seed"] += 1
        path.write_text(json.dumps(value))
    elif change == "tokenizer":
        identity = {"changed_tokenizer": True}
    else:
        with raw.open("ab") as stream:
            stream.write(b"changed")
    with pytest.raises(PrepError):
        verify(root, "unit1", tokenizer, identity, raw=raw)


def test_existing_runs_never_overwritten(prepared):
    root, _, tokenizer, identity, options = prepared
    with pytest.raises(PrepError, match="already_exists"):
        pipeline.prepare(root, "unit1", tokenizer, identity, **options)


def test_duplicate_id_fails_metadata_scan(tmp_path):
    raw = tmp_path / "duplicate.csv"
    value = dataclasses.asdict(population(1)[0])
    value.update(title="", prompt="", generation="not examined")
    with raw.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, COLUMNS)
        writer.writeheader()
        writer.writerows([value, value])
    with pytest.raises(PrepError, match="duplicate_row_identity"):
        index_metadata(raw, tmp_path / "index.sqlite", Budget(tmp_path / "budget"))


def test_guards_reject_weight_reads_imports_and_connections():
    code = """
import pathlib, socket, sys
from litmus.data_prep.acquisition import PrepError
from litmus.data_prep.guards import preparation_guards
with preparation_guards() as attempts:
    for operation in (lambda: pathlib.Path('model.safetensors').read_bytes(),
                      lambda: __import__('torch'),
                      lambda: socket.socket().connect(('127.0.0.1', 9))):
        try:
            operation()
        except PrepError:
            pass
        else:
            raise AssertionError('operation was not blocked')
assert attempts == {'weight_file_access': 1, 'forbidden_import': 1, 'connections': 1}
assert 'torch' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


def reconciliation_case(prepared, monkeypatch):
    root, _, _, _, _ = prepared
    envelope, _, _ = validate_manifest(root / "eval/manifests/r1e/unit1")
    historical = envelope["payload"]["source_sha256"]
    current = {**historical, "src/litmus/data_prep/acquisition.py": "corrected"}
    monkeypatch.setattr(pipeline, "source_identity", lambda root: current)
    record = {
        "schema_version": 1,
        "historical_manifest_sha256": envelope["manifest_sha256"],
        "historical_source_sha256": historical,
        "verification_source_sha256": current,
        "changed_sources": ["src/litmus/data_prep/acquisition.py"],
    }
    path = root / "reconciliation.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path, record


def test_historical_source_requires_explicit_exact_reconciliation(
    prepared, monkeypatch
):
    root, raw, tokenizer, identity, _ = prepared
    output = root / "eval/manifests/r1e/unit1"
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    path, _ = reconciliation_case(prepared, monkeypatch)
    with pytest.raises(PrepError, match="preparation_source_identity_changed"):
        verify(root, "unit1", tokenizer, identity, raw=raw)
    result = verify(
        root, "unit1", tokenizer, identity, raw=raw, source_reconciliation=path
    )
    assert result["status"] == "PASS"
    assert (
        result["source_version"]["mode"] == "explicit_historical_source_reconciliation"
    )
    assert result["source_version"]["record_sha256"] == file_hash(path)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


@pytest.mark.parametrize(
    "change", ["manifest", "historical", "current", "list", "selection", "extra"]
)
def test_reconciliation_does_not_ignore_source_tampering(prepared, monkeypatch, change):
    from litmus.data_prep.verification import verify_source_version

    root, _, _, _, _ = prepared
    path, record = reconciliation_case(prepared, monkeypatch)
    current = dict(record["verification_source_sha256"])
    if change == "manifest":
        record["historical_manifest_sha256"] = "wrong"
    elif change == "historical":
        record["historical_source_sha256"] = {"unit": "wrong"}
    elif change == "current":
        current["src/litmus/data_prep/acquisition.py"] = "changed again"
    elif change == "list":
        record["changed_sources"] = []
    elif change == "selection":
        current["unit"] = "changed selection"
        record["verification_source_sha256"] = dict(current)
        record["changed_sources"] = sorted(
            ["unit", "src/litmus/data_prep/acquisition.py"]
        )
    else:
        current["extra"] = "new source"
        record["verification_source_sha256"] = dict(current)
        record["changed_sources"] = sorted(
            ["extra", "src/litmus/data_prep/acquisition.py"]
        )
    monkeypatch.setattr(pipeline, "source_identity", lambda root: current)
    path.write_text(json.dumps(record), encoding="utf-8")
    envelope, _, _ = validate_manifest(root / "eval/manifests/r1e/unit1")
    with pytest.raises(PrepError, match="source_reconciliation_mismatch"):
        verify_source_version(root, envelope, path)


def test_verifier_cli_requires_separate_receipt_and_preserves_existing(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/verify_raid_manifest.py"
    first = subprocess.run(
        [sys.executable, str(script), "--source-reconciliation", "unused.json"],
        capture_output=True,
        text=True,
    )
    assert first.returncode == 2
    assert "requires a new --output" in first.stderr
    output = tmp_path / "existing.json"
    output.write_bytes(b"original receipt")
    second = subprocess.run(
        [sys.executable, str(script), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert second.returncode != 0
    assert "verification_receipt_already_exists" in second.stderr
    assert output.read_bytes() == b"original receipt"
