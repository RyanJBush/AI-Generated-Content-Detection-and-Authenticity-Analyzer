"""R1-C2: --quality report/CLI integration (model-free)."""
import json
import pathlib

import pytest

from litmus import report as report_mod
from litmus.cli import main
from litmus.quality.observers import OBSERVER_IDS, RepeatedWord3Grams, build_observers
from litmus.schemas import (
    OriginEvidence,
    OriginResult,
    Segment,
    from_json,
    to_json,
)

HERE = pathlib.Path(__file__).parent
INPUTS = HERE / "fixtures" / "inputs"
GOLDEN = HERE / "golden"
GOLDEN_CASES = [
    "text.txt", "whitespace.txt", "empty.txt", "bom_only.txt", "bad_utf8.txt",
    "image.jpg", "image.png", "image.webp", "archive.zip",
]


def cli(capsys, *args):
    code = main(["analyze", *map(str, args)])
    return code, capsys.readouterr().out


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


# --- default off: byte-identical output ---

@pytest.mark.parametrize("name", GOLDEN_CASES)
def test_default_and_off_are_byte_identical_to_golden(capsys, name):
    _, omitted = cli(capsys, INPUTS / name)
    _, off = cli(capsys, INPUTS / name, "--quality", "off")
    assert omitted == off
    # Golden files are committed with LF; core.autocrlf may check them out
    # with CRLF, so compare after undoing that conversion only
    golden = (GOLDEN / (name.replace(".", "_") + ".json")).read_bytes()
    assert omitted.encode("utf-8") == golden.replace(b"\r\n", b"\n")


# --- quality on ---

def test_quality_on_text_segment(capsys):
    code, out = cli(capsys, INPUTS / "quality.txt", "--quality", "on")
    assert code == 0
    rep = json.loads(out)
    (seg,) = rep["segments"]
    assert [q["observer_id"] for q in seg["quality"]] == list(OBSERVER_IDS)
    assert [q["count"] for q in seg["quality"]] == [2, 3, 8, 2]
    for line in report_mod.QUALITY_REPORT_LIMITATIONS:
        assert line in rep["limitations"]
    assert ("quality observations do not establish AI origin and never affect "
            "origin results") in rep["limitations"]


@pytest.mark.parametrize("name", ["image.png", "image.jpg", "image.webp"])
def test_quality_on_image_keeps_empty_quality(capsys, name):
    code, out = cli(capsys, INPUTS / name, "--quality", "on")
    assert code == 0
    assert json.loads(out)["segments"][0]["quality"] == []


def test_quality_on_whitespace_only(capsys):
    _, out = cli(capsys, INPUTS / "whitespace.txt", "--quality", "on")
    for q in json.loads(out)["segments"][0]["quality"]:
        assert (q["status"], q["count"], q["rate_per_100_words"]) == (
            "none_found", 0, None)


def test_quality_on_changes_only_quality_and_limitations(capsys):
    _, off = cli(capsys, INPUTS / "quality.txt")
    _, on = cli(capsys, INPUTS / "quality.txt", "--quality", "on")
    off, on = json.loads(off), json.loads(on)
    assert on["limitations"] == off["limitations"] + list(
        report_mod.QUALITY_REPORT_LIMITATIONS)
    for rep in (off, on):
        rep.pop("limitations")
        rep["segments"][0].pop("quality")
    assert on == off


# --- origin separation with a deterministic stub origin analyzer ---

def stub_origin(text):
    return OriginEvidence(
        method_id="stub", method_version="1", result=OriginResult.INCONCLUSIVE,
        raw_score=0.8125, score_direction="lower_means_more_machine",
        reasons=["stub"], limitations=["stub limitation"],
        details={"n": len(text), "nested": {"a": [1, 2.5, None]}})


@pytest.mark.parametrize("name", ["quality.txt", "text.txt", "whitespace.txt",
                                  "image.png"])
def test_origin_bytes_identical_with_quality_off_and_on(name):
    path = str(INPUTS / name)
    off = report_mod.run_analysis(path, stub_origin)
    on = report_mod.run_analysis(path, stub_origin, build_observers())
    assert len(off["segments"]) == len(on["segments"]) == 1
    for a, b in zip(off["segments"], on["segments"]):
        assert canonical(a["origin"]) == canonical(b["origin"])


def test_origin_bytes_identical_when_an_observer_raises(monkeypatch):
    path = str(INPUTS / "quality.txt")
    off = report_mod.run_analysis(path, stub_origin)

    def boom(self, text, words):
        raise ValueError("injected")

    monkeypatch.setattr(RepeatedWord3Grams, "observe", boom)
    on = report_mod.run_analysis(path, stub_origin, build_observers())
    assert canonical(off["segments"][0]["origin"]) == canonical(
        on["segments"][0]["origin"])
    statuses = [q["status"] for q in on["segments"][0]["quality"]]
    assert statuses == ["observed", "observed", "error", "observed"]


def test_cli_exit_0_when_an_observer_raises(capsys, monkeypatch):
    def boom(self, text, words):
        raise RuntimeError("injected")

    monkeypatch.setattr(RepeatedWord3Grams, "observe", boom)
    code, out = cli(capsys, INPUTS / "quality.txt", "--quality", "on")
    assert code == 0
    quality = json.loads(out)["segments"][0]["quality"]
    err = quality[2]
    assert err["status"] == "error" and err["count"] is None
    assert "error=RuntimeError" in err["notes"]
    assert [q["count"] for q in quality] == [2, 3, None, 2]


# --- round trip ---

def test_report_with_quality_round_trips():
    rep = report_mod.run_analysis(str(INPUTS / "quality.txt"), None,
                                  build_observers())
    seg_json = rep["segments"][0]
    seg = from_json(Segment, seg_json)
    assert len(seg.quality) == 4
    assert to_json(seg) == seg_json
    assert from_json(Segment, to_json(seg)) == seg


def test_round_trip_with_capped_spans_and_error_record(monkeypatch, tmp_path):
    src = tmp_path / "many.txt"
    src.write_bytes(b"perhaps " * 1200)
    monkeypatch.setattr(RepeatedWord3Grams, "observe",
                        lambda self, t, w: (_ for _ in ()).throw(KeyError("x")))
    rep = report_mod.run_analysis(str(src), None, build_observers())
    seg_json = rep["segments"][0]
    assert to_json(from_json(Segment, seg_json)) == seg_json
    hedges = seg_json["quality"][1]
    assert hedges["count"] == 1200 and len(hedges["spans"]) == 1000
    assert seg_json["quality"][2]["status"] == "error"
