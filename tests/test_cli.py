"""Model-free CLI tests: the model loader is injected with fakes."""
import json

from fakes import fake_pair

from litmus import config
from litmus.cli import main


def fake_load(calls):
    def load(pair, device, dtype):
        calls.append((pair, device, dtype))
        return fake_pair()
    return load


def test_score_file_prints_report_without_calibration(tmp_path, capsys):
    path = tmp_path / "sample.txt"
    text = "Line one, studies show.\r\n" + " ".join(["word"] * 80) + "\r\nPerhaps.\r\n"
    path.write_bytes(text.encode("utf-8"))
    calls = []
    code = main(["score", str(path), "--calibration-dir", str(tmp_path / "none")], load=fake_load(calls))
    assert code == 0
    assert calls == [(config.DEFAULT_PAIR, "auto", "float32")]
    report = json.loads(capsys.readouterr().out)
    assert report["binoculars"]["flag"] == "no_calibration"
    assert report["binoculars"]["calibration"] is None
    assert report["binoculars"]["score"] is not None
    assert "not a probability" in report["binoculars"]["note"]
    assert report["disclaimer"]
    # Offsets index the file's characters with \r\n preserved (no newline translation).
    start, end = report["slop"]["features"]["hedges"]["spans"][0]
    assert text[start:end] == "Perhaps"


def test_options_and_output_file(tmp_path, capsys):
    path = tmp_path / "sample.txt"
    path.write_text("Too short to score.", encoding="utf-8")
    out = tmp_path / "report.json"
    calls = []
    code = main(["score", str(path), "--pair", "1.5b", "--device", "cpu", "--dtype", "bfloat16",
                 "--output", str(out)], load=fake_load(calls))
    assert code == 0 and calls == [("1.5b", "cpu", "bfloat16")]
    printed = json.loads(capsys.readouterr().out)
    assert json.loads(out.read_text(encoding="utf-8")) == printed
    assert printed["binoculars"]["flag"] == "too_short"


def test_unreadable_file_returns_error_without_loading_models(tmp_path, capsys):
    calls = []
    assert main(["score", str(tmp_path / "missing.txt")], load=fake_load(calls)) == 2
    assert calls == []
    assert "cannot read" in capsys.readouterr().err
    bad = tmp_path / "latin1.txt"
    bad.write_bytes("caf\xe9".encode("latin-1"))
    assert main(["score", str(bad)], load=fake_load(calls)) == 2
    assert calls == []
