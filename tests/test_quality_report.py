"""R1-C2: --quality report/CLI integration (model-free)."""
import json
import pathlib

import pytest

from litmus import cli as cli_mod
from litmus import report as report_mod
from litmus.cli import main
from litmus.quality import lexicon as lex_mod
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


# --- lexicon initialization failures (R1-C2 corrections, fix 1) ---

def stub_cli(capsys, monkeypatch, *args):
    """Full CLI path, with the deterministic stub origin analyzer."""
    real = report_mod.run_analysis
    monkeypatch.setattr(cli_mod, "run_analysis",
                        lambda path, origin, observers: real(path, stub_origin,
                                                             observers))
    code, out = cli(capsys, INPUTS / "quality.txt", *args)
    return code, json.loads(out)


def fail_resource(monkeypatch, name, make_error):
    """The packaged resource read fails for lexicon `name` only."""
    real = lex_mod.resource_bytes

    def fake(n):
        if n == name:
            raise make_error(n)
        return real(n)

    monkeypatch.setattr(lex_mod, "resource_bytes", fake)


def check_isolated(capsys, monkeypatch, failing, inject):
    _, baseline = stub_cli(capsys, monkeypatch, "--quality", "on")
    _, off = stub_cli(capsys, monkeypatch, "--quality", "off")
    inject()
    code, rep = stub_cli(capsys, monkeypatch, "--quality", "on")
    assert code == 0
    quality = {q["observer_id"]: q for q in rep["segments"][0]["quality"]}
    expected = {q["observer_id"]: q for q in baseline["segments"][0]["quality"]}
    assert list(quality) == list(OBSERVER_IDS)
    err = quality.pop(failing)
    assert (err["status"], err["count"], err["rate_per_100_words"], err["spans"]) == (
        "error", None, None, [])
    expected.pop(failing)
    assert quality == expected
    assert canonical(rep["segments"][0]["origin"]) == canonical(
        off["segments"][0]["origin"])
    assert rep["limitations"] == baseline["limitations"]
    return err


def test_permission_error_on_one_lexicon_is_isolated(capsys, monkeypatch):
    err = check_isolated(capsys, monkeypatch, "hedges", lambda: fail_resource(
        monkeypatch, "hedges", lambda n: PermissionError(13, "denied", n)))
    assert err["notes"] == ["observer_version=1", "error=PermissionError"]


def test_file_not_found_on_one_lexicon_is_isolated(capsys, monkeypatch):
    err = check_isolated(
        capsys, monkeypatch, "claim_phrases_to_inspect", lambda: fail_resource(
            monkeypatch, "claim_phrases_to_inspect",
            lambda n: FileNotFoundError(2, "missing", n)))
    assert err["notes"] == ["observer_version=1", "error=FileNotFoundError"]


def test_invalid_lexicon_for_one_observer_is_isolated(capsys, monkeypatch):
    real = lex_mod.resource_bytes

    def header_only(n):
        data = real(n)
        if n == "stock_phrases":  # header lines only: no valid entries
            return b"".join(data.splitlines(keepends=True)[:6])
        return data

    err = check_isolated(capsys, monkeypatch, "stock_phrases",
                         lambda: monkeypatch.setattr(lex_mod, "resource_bytes",
                                                     header_only))
    assert err["notes"] == ["observer_version=1",
                            "lexicon_invalid=no valid entries"]


def test_missing_file_at_the_read_keeps_its_lexicon_error(capsys, monkeypatch):
    # resource_bytes turns a FileNotFoundError from the file read itself into
    # LexiconError("... is not packaged"); that existing behavior is kept
    real = pathlib.Path.read_bytes

    def read_bytes(self):
        if self.name == "hedges.txt":
            raise FileNotFoundError(2, "missing", str(self))
        return real(self)

    err = check_isolated(capsys, monkeypatch, "hedges", lambda: monkeypatch.setattr(
        pathlib.Path, "read_bytes", read_bytes))
    assert err["notes"] == ["observer_version=1",
                            "lexicon_invalid=lexicon 'hedges' is not packaged"]


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
