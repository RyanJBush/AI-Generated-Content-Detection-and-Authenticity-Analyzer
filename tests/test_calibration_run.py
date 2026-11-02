"""Synthetic input/journal/freeze tests; no real text scoring or network."""

import contextlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_scoring_identity import fields

from litmus import calibration_run as run
from litmus.data_prep.keys import canonical
from litmus.scorer.calibration import (
    CalibrationError,
    envelope,
    scoring_config_hash,
    sha,
    validate_freeze,
)


@pytest.fixture
def synthetic(tmp_path):
    rows = []
    for i in range(203):
        data = (f"constructed {i} " * 20).encode()
        digest = sha(data)
        row = {
            "id": str(i),
            "source_id": "s" + str(i),
            "split": "dev",
            "role": "human" if i < 201 else "machine",
            "attack": "none",
            "raw_text_sha256": digest,
            "scored_window_sha256": "a" * 64,
            "text_blob": "texts/" + digest + ".txt",
            "tokens_total": 64,
            "tokens_scored": 64,
            "truncated": False,
            "scored_char_range": [0, 64],
        }
        path = tmp_path / "data/raid/prepared/primary" / row["text_blob"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        rows.append(row)
    projection = b"".join(canonical(r) + b"\n" for r in rows)
    f = fields()
    header = {
        "schema_version": "r1f-dev-run-v1",
        "run_id": "unit",
        "created": "2026-11-01T00:00:00+00:00",
        "scoring_config": f,
        "scoring_config_hash": scoring_config_hash(f),
        "prepared_manifest_sha256": "b" * 64,
        "dev_set_id": sha(projection),
        "reconciliation_sha256": "c" * 64,
        "implementation_commit": "d" * 40,
        "source_files_sha256": {"unit.py": "e" * 64},
        "models_manifest_sha256": "f" * 64,
    }

    def score(row):
        return {
            **{
                k: row[k]
                for k in (
                    "id",
                    "source_id",
                    "split",
                    "role",
                    "attack",
                    "raw_text_sha256",
                    "scored_window_sha256",
                )
            },
            "scoring_config_hash": header["scoring_config_hash"],
            "status": "valid",
            "stats": {
                "score": 1.0,
                "nll_performer": 2.0,
                "xent": 2.0,
                "n_input_tokens": 64,
                "n_target_tokens": 63,
            },
            "scored_window": {
                k: row[k]
                for k in (
                    "tokens_total",
                    "tokens_scored",
                    "truncated",
                    "scored_char_range",
                )
            },
            "reasons": [],
        }

    return tmp_path, rows, projection, header, score


def test_dev_projection_and_no_test_file_access(synthetic):
    root, rows, projection, _, _ = synthetic
    test = dict(rows[0], id="test", split="test", text_blob="texts/test-only.txt")
    selected, data = run.dev_projection([*rows, test])
    assert selected == rows and data == projection
    with pytest.raises(CalibrationError, match="nondev_or_unknown"):
        run.read_dev_text(root, test, rows)
    test_path = root / "data/raid/prepared/primary/texts/test-only.txt"
    test_path.write_bytes(b"constructed held-out probe")
    with run.scoring_guards(root, rows) as attempts:
        assert run.read_dev_text(root, rows[0], rows).startswith("constructed")
        with pytest.raises(CalibrationError, match="nondev_data_access"):
            test_path.read_bytes()
        import socket

        with pytest.raises(CalibrationError, match="network_forbidden"):
            socket.socket().connect(("127.0.0.1", 9))
    assert attempts == {"connections": 1, "forbidden_data_access": 1}


def test_input_hash_path_injection_and_duplicate_ids(synthetic):
    root, rows, _, _, _ = synthetic
    with pytest.raises(CalibrationError, match="duplicate_input"):
        run.dev_projection([rows[0], rows[0]])
    with pytest.raises(CalibrationError, match="unknown_input_split"):
        run.dev_projection([dict(rows[0], split="other")])
    for replacement in ("../../../../escape", "texts/missing.txt"):
        changed = dict(rows[0], text_blob=replacement)
        with pytest.raises((CalibrationError, FileNotFoundError)):
            run.read_dev_text(root, changed, [changed])
    path = root / "data/raid/prepared/primary" / rows[0]["text_blob"]
    path.write_bytes(b"tampered")
    with pytest.raises(CalibrationError, match="raw_blob_hash_mismatch"):
        run.read_dev_text(root, rows[0], rows)


def test_full_journal_reassembly_resume_and_independent_threshold(synthetic):
    root, rows, projection, header, score = synthetic
    directory = root / "run"
    actual = run.run_rows(directory, rows, projection, header, score)
    seen = []
    assert (
        run.run_rows(directory, rows, projection, header, lambda r: seen.append(r))
        == actual
    )
    assert seen == []
    old, ordered, failures, counts, artifact = run.verify_dev(
        directory, rows, projection
    )
    assert old == header and ordered == actual and failures == []
    assert counts["eligible_development_negatives"] == 201
    assert artifact["payload"]["threshold_c"] == -1.0
    assert artifact["payload"]["above"] == 0
    assert (
        "freeze_sha256" not in artifact and "freeze_sha256" not in artifact["payload"]
    )
    assert not (directory / "writer.lock").exists()


@pytest.mark.parametrize(
    "phase", ["before_attempt", "after_attempt", "after_completion"]
)
def test_interruption_boundaries_skip_only_durable_completions(synthetic, phase):
    root, rows, projection, header, score = synthetic
    directory = root / "run"
    directory.mkdir()
    run.new_json(directory / "header.json", header)
    run.new_bytes(directory / "dev_input.jsonl", projection)
    if phase != "before_attempt":
        run.append_event(
            directory / "journal.jsonl",
            {"event": "attempt", "id": "0", "data": header["scoring_config_hash"]},
        )
    if phase == "after_completion":
        run.append_event(
            directory / "journal.jsonl",
            {"event": "completion", "id": "0", "data": score(rows[0])},
        )
    calls = []

    def compute(row):
        calls.append(row["id"])
        return score(row)

    run.run_rows(directory, rows, projection, header, compute)
    assert calls[0] == ("1" if phase == "after_completion" else "0")
    assert len(calls) == len(rows) - (phase == "after_completion")


def test_truncated_tail_requires_explicit_preserved_recovery(synthetic):
    root, rows, projection, header, score = synthetic
    directory = root / "run"
    directory.mkdir()
    run.new_json(directory / "header.json", header)
    run.new_bytes(directory / "dev_input.jsonl", projection)
    event = {"event": "attempt", "id": "0", "data": header["scoring_config_hash"]}
    run.append_event(directory / "journal.jsonl", event)
    with (directory / "journal.jsonl").open("ab") as stream:
        stream.write(b'{"event":"comple')
    before = (directory / "journal.jsonl").read_bytes()
    with pytest.raises(CalibrationError, match="journal_truncated"):
        run.run_rows(directory, rows, projection, header, score)
    run.recover_tail(directory, rows, header)
    assert next(directory.glob("journal.damaged.*.jsonl")).read_bytes() == before
    run.run_rows(directory, rows, projection, header, score)
    assert run.verify_dev(directory, rows, projection)[3]["valid_rows"] == len(rows)


@pytest.mark.parametrize(
    "kind", ["unknown", "duplicate", "gap", "corrupt", "header", "input", "scores"]
)
def test_journal_tampering_and_incompatible_resume_fail(synthetic, kind):
    root, rows, projection, header, score = synthetic
    directory = root / "run"
    run.run_rows(directory, rows, projection, header, score)
    path = directory / "journal.jsonl"
    if kind == "header":
        header = dict(header, scoring_config_hash="0" * 64)
    elif kind == "input":
        (directory / "dev_input.jsonl").write_bytes(b"wrong")
    elif kind == "scores":
        (directory / "scores.jsonl").write_bytes(b"wrong")
    elif kind == "duplicate":
        run.append_event(
            path, {"event": "attempt", "id": "0", "data": header["scoring_config_hash"]}
        )
    elif kind == "unknown":
        path.write_bytes(
            canonical({"event": "attempt", "id": "test-only", "data": "x"}) + b"\n"
        )
    elif kind == "gap":
        path.write_bytes(
            canonical(
                {"event": "attempt", "id": "1", "data": header["scoring_config_hash"]}
            )
            + b"\n"
        )
    else:
        path.write_bytes(b"{corrupt}\n" + path.read_bytes())
    with pytest.raises(CalibrationError):
        run.run_rows(directory, rows, projection, header, score)


def test_lock_ownership_and_no_overwrites(synthetic):
    root, rows, _, _, _ = synthetic
    with run.writer_lock(root / "run"):
        with pytest.raises(CalibrationError, match="writer_lock_exists"):
            with run.writer_lock(root / "run"):
                pytest.fail("second writer")
    path = root / "receipt.json"
    run.new_json(path, {"original": True})
    with pytest.raises(FileExistsError):
        run.new_json(path, {"changed": True})
    assert run.read_json(path) == {"original": True}
    with pytest.raises(CalibrationError):
        with run.scoring_guards(root, [dict(rows[0], split="test")]):
            pytest.fail("test guard")


def test_terminal_numerical_failure_stops_and_is_not_retried(synthetic):
    root, rows, projection, header, score = synthetic
    calls = []

    def broken(row):
        calls.append(row["id"])
        raise CalibrationError("constructed numerical failure")

    with pytest.raises(CalibrationError):
        run.run_rows(root / "run", rows, projection, header, broken)
    assert calls == ["0"]
    with pytest.raises(CalibrationError, match="terminal_failure_requires_review"):
        run.run_rows(root / "run", rows, projection, header, score)
    assert not (root / "run/scores.jsonl").exists()


def test_valid_negative_count_gate_and_positive_failure_independence(synthetic):
    root, rows, projection, header, score = synthetic
    directory = root / "run"
    run.run_rows(directory, rows, projection, header, score)
    records = [score(r) for r in rows]
    for index in (201,):
        records[index].update(
            status="failed", stats=None, scored_window=None, reasons=["constructed"]
        )

    def rewrite():
        events = []
        for row, record in zip(rows, records, strict=True):
            events.extend(
                [
                    {
                        "event": "attempt",
                        "id": row["id"],
                        "data": header["scoring_config_hash"],
                    },
                    {"event": "completion", "id": row["id"], "data": record},
                ]
            )
        (directory / "journal.jsonl").write_bytes(
            b"".join(canonical(e) + b"\n" for e in events)
        )
        (directory / "scores.jsonl").write_bytes(
            b"".join(canonical(r) + b"\n" for r in records)
        )

    rewrite()
    assert (
        run.verify_dev(directory, rows, projection)[3]["eligible_development_negatives"]
        == 201
    )
    for i in range(2):
        records[i].update(
            status="failed", stats=None, scored_window=None, reasons=["constructed"]
        )
    rewrite()
    with pytest.raises(CalibrationError, match="insufficient_development_negatives"):
        run.verify_dev(directory, rows, projection)


def test_real_projection_metadata_only_and_historical_reconciliation():
    root = Path(__file__).resolve().parents[1]
    rows, projection, version = run.load_dev(root)
    assert len(rows) == 1484 and run.sha(projection) == run.DEV
    assert all(r["split"] == "dev" for r in rows)
    assert version["mode"] == "explicit_historical_source_reconciliation"


def test_freeze_one_way_binding_and_mismatch_refusal(synthetic, monkeypatch):
    root, rows, projection, header, score = synthetic
    directory = root / "run"
    run.run_rows(directory, rows, projection, header, score)
    _, _, _, _, artifact = run.verify_dev(directory, rows, projection)
    lexicons = {
        n: {"version": 1, "sha256": "a" * 64}
        for n in ("claim_phrases_to_inspect", "hedges", "stock_phrases")
    }
    monkeypatch.setattr(
        run, "lexicon_identity", lambda repo: (lexicons, {"quality.py": "b" * 64})
    )
    evidence = root / "evidence.json"
    evidence.write_bytes(b'{"constructed":true}\n')
    artifact_bytes = canonical(artifact) + b"\n"
    freeze = run.assemble_freeze(
        root, directory, artifact, artifact_bytes, b"", [evidence]
    )
    expected = freeze["payload"]
    assert expected["calibration_file_sha256"] == sha(artifact_bytes)
    assert "freeze_sha256" not in json.dumps(artifact)
    for key, bad in (
        ("threshold_c", 2.0),
        ("scoring_config_hash", "f" * 64),
        ("dev_set_id", "f" * 64),
        ("one_percent_enabled", True),
        ("historical_transfer_compliance_proven", True),
    ):
        changed = envelope(dict(expected, **{key: bad}), "freeze_sha256")
        with pytest.raises(CalibrationError):
            validate_freeze(changed, artifact, expected=expected)
    altered = dict(
        expected, lexicons={**lexicons, "hedges": {"version": 2, "sha256": "c" * 64}}
    )
    with pytest.raises(CalibrationError, match="freeze_runtime_identity_mismatch"):
        validate_freeze(envelope(altered, "freeze_sha256"), artifact, expected=expected)
    evidence.write_bytes(b"changed")
    assert (
        run.assemble_freeze(root, directory, artifact, artifact_bytes, b"", [evidence])
        != freeze
    )


def test_committed_freeze_proof_rejects_uncommitted_or_tampered(tmp_path, monkeypatch):
    path = tmp_path / "freeze.json"
    path.write_bytes(b"original")
    monkeypatch.setattr(
        run, "git", lambda repo, *args: b"other" if args[0] == "show" else b"d" * 40
    )
    with pytest.raises(CalibrationError, match="uncommitted_or_tampered"):
        run.verify_committed(tmp_path, [path])


def test_header_only_interruption_can_finish_immutable_projection(synthetic):
    root, rows, projection, header, score = synthetic
    directory = root / "run"
    directory.mkdir()
    run.new_json(directory / "header.json", header)
    run.run_rows(directory, rows, projection, header, score)
    assert (directory / "dev_input.jsonl").read_bytes() == projection


@pytest.mark.parametrize("bad", ["window", "hash", "profile", "nan"])
def test_production_scoring_seam_rejects_identity_or_numerical_errors(synthetic, bad):
    root, rows, _, header, _ = synthetic

    class Tokenizer:
        def __call__(self, text, **kwargs):
            return {
                "input_ids": list(range(64)),
                "offset_mapping": [(i, i + 1) for i in range(64)],
            }

    row = dict(rows[0])
    text = run.read_dev_text(root, row, rows)
    observed, errors = run.assess(text, Tokenizer())
    assert not errors
    row.update(observed)
    details = {
        "scoring_config_hash": header["scoring_config_hash"],
        "scoring_config": header["scoring_config"],
        "execution_profile_complete": True,
        "execution_profile_failures": {},
        "nll_performer": 2.0,
        "xent": 2.0,
        "n_input_tokens": 64,
        "n_target_tokens": 63,
        "scored_window": {
            k: row[k]
            for k in ("tokens_total", "tokens_scored", "truncated", "scored_char_range")
        },
    }
    if bad == "hash":
        details["scoring_config_hash"] = "0" * 64
    if bad == "profile":
        details["execution_profile_complete"] = False
    if bad == "window":
        row["scored_window_sha256"] = "f" * 64

    def analyze(pair, text, *, apply_calibration):
        assert apply_calibration is False
        return SimpleNamespace(
            raw_score=float("nan") if bad == "nan" else 1.0,
            details=details,
            reasons=["calibration_disabled_for_creation"],
            result=SimpleNamespace(value="inconclusive"),
        )

    session = {
        "pair": SimpleNamespace(tokenizer=Tokenizer()),
        "analyzer": SimpleNamespace(score_text=analyze),
        "fields": header["scoring_config"],
        "scoring_config_hash": header["scoring_config_hash"],
    }
    with pytest.raises(CalibrationError):
        run.score_row(root, row, [row], session)


def test_constructed_cli_pipeline_preflight_dev_audit_and_freeze(
    synthetic, monkeypatch
):
    root, rows, projection, header, score = synthetic
    monkeypatch.setattr(run, "__file__", str(root / "src/litmus/calibration_run.py"))
    monkeypatch.setattr(run, "DEV", sha(projection))
    monkeypatch.setattr(
        run, "load_dev", lambda repo: (rows, projection, {"mode": "constructed"})
    )
    snapshot = {k: header[k] for k in ("implementation_commit", "source_files_sha256")}
    monkeypatch.setattr(run, "code_snapshot", lambda repo: snapshot)
    synthetic_path = root / "eval/inputs/r1b2/len512_00.txt"
    synthetic_path.parent.mkdir(parents=True)
    synthetic_path.write_bytes(b"constructed synthetic input")
    monkeypatch.setattr(run, "git", lambda repo, *args: synthetic_path.read_bytes())

    @contextlib.contextmanager
    def session(repo, items):
        assert items == rows
        value = {
            "fields": header["scoring_config"],
            "scoring_config_hash": header["scoring_config_hash"],
            "models_manifest_sha256": header["models_manifest_sha256"],
            "guards": {"connections": 0, "forbidden_data_access": 0},
            "telemetry": {},
        }
        yield value

    monkeypatch.setattr(run, "production_session", session)
    monkeypatch.setattr(
        run,
        "synthetic_result",
        lambda *a: {"stats": {"score": 1.0}, "scored_window": {}},
    )
    monkeypatch.setattr(run, "score_row", lambda repo, row, items, session: score(row))
    lexicons = {
        n: {"version": 1, "sha256": "a" * 64}
        for n in ("claim_phrases_to_inspect", "hedges", "stock_phrases")
    }
    monkeypatch.setattr(
        run, "lexicon_identity", lambda repo: (lexicons, {"quality.py": "b" * 64})
    )
    checks = root / "eval/results/r1f_implementation_verification.json"
    run.new_json(checks, {"status": "PASS", "evidence_kind": "constructed"})
    run.main(["preflight", "--output", "eval/results/r1f/preflight_a.json"])
    run.main(["preflight", "--output", "eval/results/r1f/preflight_b.json"])
    run.main(["score-dev"])
    run.main(["audit-dev", "--output", "eval/results/r1f/dev_repeat_audit.json"])
    run.main(["verify-dev", "--output", "eval/results/r1f/dev_verified.json"])
    run.main(["freeze", "--output", "eval/freezes/r1f_freeze.json"])
    freeze = run.read_json(root / "eval/freezes/r1f_freeze.json")
    artifact_path = next((root / "calibrations").glob("*.json"))
    artifact = run.read_json(artifact_path)
    assert freeze["payload"]["calibration_file_sha256"] == sha(
        artifact_path.read_bytes()
    )
    assert "freeze_sha256" not in json.dumps(artifact)
    monkeypatch.setattr(run, "verify_committed", lambda repo, paths: "e" * 40)
    run.main(["verify-freeze"])
    with pytest.raises(CalibrationError, match="output_already_exists"):
        run.main(["freeze", "--output", "eval/freezes/r1f_freeze.json"])
