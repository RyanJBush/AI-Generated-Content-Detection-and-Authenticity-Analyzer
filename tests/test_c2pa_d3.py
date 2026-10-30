"""D3 opt-in reporting; real local fixtures and injected error paths."""
import io
import json
import pathlib
import subprocess
import sys
import threading

import pytest
from PIL import Image
from test_offline_c2pa import _remote_reference_jpeg

from litmus.cli import main
from litmus.report import run_analysis
from litmus.schemas import Segment, from_json, to_json

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/c2pa"
INPUTS = ROOT / "tests/fixtures/inputs"


@pytest.mark.parametrize("ext", ["jpg", "png", "webp"])
def test_default_and_off_bytes_unchanged(ext, capsys):
    path = str(INPUTS / f"image.{ext}")
    assert main(["analyze", path]) == 0
    omitted = capsys.readouterr().out
    assert main(["analyze", path, "--c2pa", "off"]) == 0
    assert capsys.readouterr().out == omitted
    golden = ROOT / f"tests/golden/image_{ext}.json"
    assert omitted == golden.read_text(encoding="utf-8")


@pytest.mark.parametrize("name,rule", [
    ("trusted_signer.jpg", 10), ("trusted_signer.png", 10),
    ("trusted_signer.webp", 10), ("no_manifest.jpg", 3),
    ("no_manifest.png", 3), ("no_manifest.webp", 3),
    ("tampered.jpg", 5), ("active_ai_declared.jpg", 8),
    ("ingredient_ai_only.jpg", 9), ("remote_reference.jpg", 4)])
def test_enabled_evidence_and_round_trip(name, rule):
    report = run_analysis(str(FIX / name), c2pa_enabled=True)
    segment = report["segments"][0]
    evidence = segment["origin"][0]
    assert evidence["method_id"] == "c2pa_provenance"
    assert evidence["raw_score"] is evidence["score_direction"] is None
    assert evidence["calibration"] is None
    assert evidence["details"]["rule"] == rule
    assert evidence["result"] != "supports_ai"
    prov = evidence["provenance"]
    assert prov["trust_list"]["anchor_count"] == 0
    assert len(prov["trust_list"]["sha256"]) == 64
    assert prov["library_versions"] == {"c2pa_python": "0.38.0", "sdk": "0.91.0"}
    assert prov["policy"] == "production"
    assert prov["settings"]["verify"]["remote_manifest_fetch"] is False
    assert evidence["details"]["settings_applied"] is True
    assert evidence["details"]["timings"]["response_seconds"] >= 0
    assert evidence["details"]["timings"]["read_seconds"] >= 0
    assert any("empty production trust" in s for s in evidence["limitations"])
    assert any("empty production trust" in s for s in report["limitations"])
    assert not any("no C2PA analysis" in s for s in report["limitations"])
    if prov["active"]:
        assert prov["active"]["signer_trust"] == "unknown"
        assert prov["active"]["timestamp"] == "absent"
        assert evidence["details"]["status_entries"]
    assert to_json(from_json(Segment, segment)) == segment
    assert json.loads(json.dumps(report)) == report


def test_text_origin_quality_and_rejected_input_unchanged():
    from litmus.report import text_origin_placeholder

    calls = []

    def scorer(text):
        calls.append(text)
        evidence = text_origin_placeholder(text)
        evidence.details["scoring_config_hash"] = "model-free-stub-hash"
        return evidence

    from litmus.quality.observers import build_observers
    observers = build_observers()
    path = str(INPUTS / "text.txt")
    off = run_analysis(path, scorer, observers)
    on = run_analysis(path, scorer, observers, c2pa_enabled=True)
    assert on == off
    assert len(calls) == 2
    assert run_analysis(str(INPUTS / "archive.zip"), c2pa_enabled=True) == (
        run_analysis(str(INPUTS / "archive.zip")))


@pytest.mark.parametrize("mode,filename", [("off", "image.jpg"),
                                          ("on", "text.txt"),
                                          ("on", "image.jpg")])
def test_fresh_process_import_isolation(mode, filename):
    code = """
import sys, threading
from litmus.report import run_analysis
run_analysis(sys.argv[1], c2pa_enabled=sys.argv[2] == 'on')
assert not any(m == 'torch' or m.startswith('torch.') or
               m == 'transformers' or m.startswith('transformers.') or
               m.startswith('litmus.scorer') for m in sys.modules)
if sys.argv[2] == 'off' or sys.argv[1].endswith('.txt'):
    assert not any(m == 'c2pa' or m.startswith('c2pa.') or
                   m.startswith('litmus.c2pa') for m in sys.modules)
    assert not any(t.name == 'litmus-c2pa-worker' for t in threading.enumerate())
"""
    result = subprocess.run([sys.executable, "-c", code,
                             str(INPUTS / filename), mode],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_activation_refusal_and_cli_error_exit(monkeypatch, capsys, tmp_path):
    from litmus.c2pa import analyzer
    monkeypatch.setattr(analyzer, "REVIEWED_OFFLINE_EVIDENCE", False)
    output = tmp_path / "report.json"
    assert main(["analyze", str(FIX / "trusted_signer.jpg"), "--c2pa", "on",
                 "-o", str(output)]) == 1
    captured = capsys.readouterr()
    assert "offline evidence" in captured.err
    assert captured.out == ""
    assert not output.exists()


def test_cli_enabled_output_and_options(tmp_path, capsys):
    args = ["analyze", str(FIX / "no_manifest.jpg"), "--c2pa", "on"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["segments"][0]["origin"][0][
        "method_id"] == "c2pa_provenance"
    target = tmp_path / "report.json"
    assert main(args + ["-o", str(target)]) == 0
    assert capsys.readouterr().out == ""
    assert json.loads(target.read_text())["segments"]
    with pytest.raises(SystemExit) as exc:
        main(args[:-1] + ["maybe"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        main(["analyze", "--help"])
    assert exc.value.code == 0
    assert "--c2pa {off,on}" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["settings", "mapping", "read", "malformed"])
def test_error_evidence_never_falls_back(monkeypatch, capsys, failure):
    from litmus.c2pa import analyzer, reader
    from litmus.c2pa.reader import ReadOutcome

    if failure == "settings":
        def reject(config):
            raise ValueError("constructed settings rejection")
        monkeypatch.setattr(reader, "build_settings", reject)
    else:
        def broken(*args):
            if failure == "read":
                raise ValueError("constructed read failure")
            return ReadOutcome("store", store=[] if failure == "malformed" else {})
        from litmus.c2pa.pipeline import analyze_c2pa
        monkeypatch.setattr(analyzer, "analyze_c2pa", lambda data, mime, **kw:
                            analyze_c2pa(data, mime, read=broken, **kw))
    assert main(["analyze", str(FIX / "trusted_signer.jpg"), "--c2pa", "on"]) == 0
    evidence = json.loads(capsys.readouterr().out)["segments"][0]["origin"][0]
    assert evidence["result"] == "error"
    assert evidence["method_id"] == "c2pa_provenance"
    assert evidence["details"]["validation_state"] is None
    assert evidence["provenance"]["active"] is None
    assert evidence["reasons"][0] == "c2pa_error"
    if failure == "settings":
        assert "c2pa_settings_rejected" in evidence["reasons"]
        assert evidence["details"]["settings_applied"] is False


def test_report_deadline_busy_and_recovery(monkeypatch):
    from litmus.c2pa import analyzer
    from litmus.c2pa.pipeline import analyze_c2pa
    from litmus.c2pa.reader import ReadOutcome
    from litmus.c2pa.worker import get_worker

    release = threading.Event()

    def blocked(*args):
        assert release.wait(3)
        return ReadOutcome("no_credentials")

    monkeypatch.setattr(analyzer, "analyze_c2pa", lambda data, mime, **kw:
                        analyze_c2pa(data, mime, read=blocked, deadline=0.02, **kw))
    path = str(FIX / "trusted_signer.jpg")
    try:
        timeout = run_analysis(path, c2pa_enabled=True)["segments"][0]["origin"][0]
        assert "c2pa_timeout" in timeout["reasons"]
        assert timeout["provenance"]["manifest_present"] is None
        assert timeout["details"]["settings_applied"] is None
        assert timeout["details"]["timings"]["read_seconds"] is None
        busy = run_analysis(path, c2pa_enabled=True)["segments"][0]["origin"][0]
        assert "c2pa_worker_busy" in busy["reasons"]
    finally:
        release.set()
    assert get_worker().wait_idle(3)
    assert run_analysis(path, c2pa_enabled=True)["segments"][0]["origin"][0][
        "result"] == "inconclusive"


@pytest.mark.parametrize("variant", ["builder", "xmp"])
def test_enabled_remote_trap_and_control(variant, c2pa_fixture_trap,
                                         tmp_path, monkeypatch):
    from litmus.c2pa import analyzer
    from litmus.c2pa.pipeline import analyze_c2pa

    trap = c2pa_fixture_trap
    path = FIX / "remote_reference.jpg"
    if variant == "xmp":
        path = tmp_path / "remote.jpg"
        path.write_bytes(_remote_reference_jpeg(trap.url + "/manifest.c2pa"))
    evidence = run_analysis(str(path), c2pa_enabled=True)["segments"][0]["origin"][0]
    assert evidence["reasons"] == ["remote_reference_only"]
    assert evidence["provenance"]["manifest_present"] == "remote_reference_only"
    assert trap.connections == []

    def control(data, mime, *, config):
        config["verify"]["remote_manifest_fetch"] = True
        config["core"]["allowed_network_hosts"] = [f"{trap.host}:{trap.port}"]
        return analyze_c2pa(data, mime, config=config)
    monkeypatch.setattr(analyzer, "analyze_c2pa", control)
    evidence = run_analysis(str(path), c2pa_enabled=True)["segments"][0]["origin"][0]
    assert evidence["result"] == "error"
    assert len(trap.connections) == 1
    assert trap.requests == ["/manifest.c2pa"]


def test_unsigned_metadata_and_result_invariance(tmp_path, monkeypatch):
    from litmus.c2pa import metadata

    path = tmp_path / "metadata.jpg"
    exif = Image.Exif()
    exif[305] = "AI generated " + "x" * 300
    exif[271], exif[272], exif[306] = "Make", "Model", "2026:10:30 00:00:00"
    Image.new("RGB", (4, 4)).save(path, exif=exif, xmp=b"<unparsed/>")
    report = run_analysis(str(path), c2pa_enabled=True)
    evidence = report["segments"][0]["origin"][0]
    unsigned = evidence["provenance"]["unsigned_metadata"]
    assert unsigned["label"] == "unverifiable; editable; not evidence"
    assert unsigned["exif"]["tag_count"] == 4
    assert len(unsigned["exif"]["fields"]["Software"]) == 256
    assert unsigned["xmp"] == {"status": "present", "byte_length": 11}
    assert evidence["result"] == "inconclusive"
    assert evidence["reasons"] == ["no_credentials"]

    def broken(*args):
        raise ValueError("constructed metadata failure")
    monkeypatch.setattr(metadata.Image, "open", broken)
    summary = metadata.summarize(path.read_bytes())
    assert summary["status"] == "unavailable"
    assert summary["exif"]["tag_count"] is None


def test_metadata_summary_never_reopens_input(monkeypatch):
    from litmus.c2pa.metadata import summarize

    data = io.BytesIO()
    Image.new("RGB", (2, 2)).save(data, format="PNG")
    monkeypatch.setattr(pathlib.Path, "open", lambda *args, **kw:
                        pytest.fail("metadata must use memory"))
    summary = summarize(data.getvalue())
    assert summary["exif"]["status"] == "absent"
    assert summary["xmp"]["status"] == "absent"


@pytest.mark.parametrize("failure", ["trust", "version"])
def test_initialization_failure_is_clear_and_does_not_write(failure, monkeypatch,
                                                           tmp_path, capsys):
    from litmus.c2pa import analyzer
    if failure == "trust":
        def broken():
            raise ValueError("invalid production trust resource")
        monkeypatch.setattr(analyzer, "load_production_trust_list", broken)
    else:
        monkeypatch.setattr(analyzer, "installed_versions", lambda: ("future", "sdk"))
    target = tmp_path / "out.json"
    assert main(["analyze", str(FIX / "trusted_signer.jpg"), "--c2pa", "on",
                 "-o", str(target)]) == 1
    output = capsys.readouterr()
    assert "initialization failed" in output.err
    assert output.out == ""
    assert not target.exists()


def test_metadata_failure_isolated_from_origin_and_validation(monkeypatch):
    def broken(self):
        raise ValueError("constructed EXIF failure")
    path = str(FIX / "active_ai_declared.jpg")
    before = run_analysis(path, c2pa_enabled=True)["segments"][0]["origin"][0]
    monkeypatch.setattr(Image.Image, "getexif", broken)
    after = run_analysis(path, c2pa_enabled=True)["segments"][0]["origin"][0]
    assert before["result"] == after["result"]
    assert before["reasons"] == after["reasons"]
    assert before["provenance"]["active"] == after["provenance"]["active"]
    summary = after["provenance"]["unsigned_metadata"]
    assert summary["exif"]["status"] == "unavailable"
    assert summary["xmp"]["status"] == "absent"
    assert summary["status"] == "partial"


def test_only_ingested_bytes_reach_image_analyzer(monkeypatch):
    from litmus import ingestion
    from litmus.c2pa import analyzer

    real_ingest = ingestion.ingest
    ing = real_ingest(str(FIX / "trusted_signer.jpg"))
    seen = []
    original = analyzer.analyze_image

    def spy(data, mime):
        assert data is ing.raw
        assert mime == ing.mime
        seen.append(True)
        return original(data, mime)
    monkeypatch.setattr("litmus.report.ingest", lambda path: ing)
    monkeypatch.setattr(analyzer, "analyze_image", spy)
    run_analysis("path-does-not-exist.jpg", c2pa_enabled=True)
    assert seen == [True]
