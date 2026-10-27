"""Golden-file tests for `litmus analyze FILE` (R0.5).

Set LITMUS_UPDATE_GOLDEN=1 to rewrite tests/golden/*.json from current output;
review the diff before committing.
"""
import json
import os
import pathlib
import socket
import subprocess
import sys

import pytest

from litmus import report as report_mod
from litmus.cli import main
from litmus.offline import NetworkAccessBlocked, SubprocessBlocked

HERE = pathlib.Path(__file__).parent
INPUTS = HERE / "fixtures" / "inputs"
GOLDEN = HERE / "golden"

CASES = [
    "text.txt", "whitespace.txt", "empty.txt", "bom_only.txt", "bad_utf8.txt",
    "image.jpg", "image.png", "image.webp", "archive.zip",
]


def _run_cli(capsys, path):
    code = main(["analyze", str(path)])
    out = capsys.readouterr().out
    return code, out


@pytest.mark.parametrize("name", CASES)
def test_cli_golden(capsys, name):
    code, out = _run_cli(capsys, INPUTS / name)
    assert code == 0
    actual = json.loads(out)

    golden_path = GOLDEN / (name.replace(".", "_") + ".json")
    if os.environ.get("LITMUS_UPDATE_GOLDEN") == "1":
        GOLDEN.mkdir(exist_ok=True)
        golden_path.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert actual == expected


EXPECTED_OUTCOMES = {
    # name: (ingestion result, reason, segment modality, origin result, origin reason)
    "text.txt": ("supported", None, "text", "inconclusive",
                 "no_text_origin_detector_in_r0"),
    "whitespace.txt": ("supported", None, "text", "inconclusive",
                       "no_nonwhitespace_content"),
    "empty.txt": ("not_supported", "empty_input", None, None, None),
    "bom_only.txt": ("not_supported", "empty_after_decoding", None, None, None),
    "bad_utf8.txt": ("not_supported", "invalid encoding", None, None, None),
    "image.jpg": ("supported", None, "image", "not_supported",
                  "c2pa_analyzer_disabled_in_r0"),
    "image.png": ("supported", None, "image", "not_supported",
                  "c2pa_analyzer_disabled_in_r0"),
    "image.webp": ("supported", None, "image", "not_supported",
                   "c2pa_analyzer_disabled_in_r0"),
    "archive.zip": ("not_supported", "documents arrive in R2", None, None, None),
}


@pytest.mark.parametrize("name", CASES)
def test_cli_report_semantics(capsys, name):
    """Independent of the golden files: the outcome each fixture must produce."""
    _, out = _run_cli(capsys, INPUTS / name)
    rep = json.loads(out)
    result, reason, modality, origin_result, origin_reason = EXPECTED_OUTCOMES[name]

    assert rep["input"]["ingestion"] == {"result": result, "reason": reason}
    cov = rep["extraction_coverage"]
    if modality is None:
        assert rep["segments"] == []
        assert cov["segments_created"] == 0
        assert cov["skipped"] == [{"item": "input", "reason": reason}]
        return

    (seg,) = rep["segments"]
    assert seg["segment_id"] == "s0" and seg["parent_id"] is None
    assert seg["modality"] == modality
    assert seg["extraction"]["status"] == "complete"
    assert seg["quality"] == []
    (origin,) = seg["origin"]
    assert origin["result"] == origin_result
    assert origin_reason in origin["reasons"]
    assert origin["limitations"]
    assert origin["raw_score"] is None and origin["calibration"] is None
    assert cov["segments_created"] == 1 and cov["skipped"] == []
    assert cov["ratio"] == 1.0 and cov["in_segments"] == cov["total"]


def test_cli_text_coverage_counts_code_points(capsys):
    _, out = _run_cli(capsys, INPUTS / "text.txt")
    rep = json.loads(out)
    text = (INPUTS / "text.txt").read_bytes().decode("utf-8")
    assert rep["extraction_coverage"]["total"] == len(text)
    assert rep["segments"][0]["local_frame"] == {
        "type": "text_codepoints", "length": len(text)}
    assert rep["segments"][0]["origin"][0]["details"] == {"scored_window": None}


def test_cli_output_option_writes_file(tmp_path, capsys):
    out_path = tmp_path / "report.json"
    code = main(["analyze", str(INPUTS / "text.txt"), "-o", str(out_path)])
    assert code == 0
    assert capsys.readouterr().out == ""
    assert json.loads(out_path.read_text(encoding="utf-8"))["segments"]


def test_cli_missing_file_exit_1(tmp_path, capsys):
    code = main(["analyze", str(tmp_path / "nope.txt")])
    assert code == 1
    assert "not a file" in capsys.readouterr().err


def test_cli_usage_error_exit_2():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_module_entry_point_runs():
    # End to end through a real interpreter process (outside the guard)
    result = subprocess.run(
        [sys.executable, "-m", "litmus.cli", "analyze", str(INPUTS / "text.txt")],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["report_schema"] == "litmus-report/r0"


# --- guards are active during analysis (A1.2, A1.3) ---

def test_subprocess_blocked_during_analysis(monkeypatch):
    def spawns(text):
        subprocess.run([sys.executable, "-c", "pass"])
    monkeypatch.setattr(report_mod, "text_origin_placeholder", spawns)
    with pytest.raises(SubprocessBlocked):
        report_mod.run_analysis(str(INPUTS / "text.txt"))


def test_network_blocked_during_analysis(monkeypatch):
    # The suite-wide guard is already active, so also check that run_analysis
    # installs its own guard (a different connect wrapper) around analysis.
    outer_connect = socket.socket.connect
    seen = {}

    def connects(text):
        seen["inner_connect"] = socket.socket.connect
        socket.create_connection(("192.0.2.1", 80), timeout=1)
    monkeypatch.setattr(report_mod, "text_origin_placeholder", connects)
    with pytest.raises(NetworkAccessBlocked):
        report_mod.run_analysis(str(INPUTS / "text.txt"))
    assert seen["inner_connect"] is not outer_connect
    assert socket.socket.connect is outer_connect
