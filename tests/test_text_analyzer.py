"""Text analyzer paths that need no models (default suite)."""
import json

from litmus.cli import main
from litmus.scorer.analyzer import BinocularsAnalyzer


def test_whitespace_only_is_inconclusive_without_loading_models(tmp_path):
    analyzer = BinocularsAnalyzer(models_dir=tmp_path / "no-models")
    ev = analyzer("  \n\t ")
    assert ev.result.value == "inconclusive"
    assert ev.reasons == ["no_nonwhitespace_content"]
    assert analyzer._pair is None


def test_missing_models_give_error_with_setup_hint(tmp_path):
    ev = BinocularsAnalyzer(models_dir=tmp_path / "no-models")("Some text.")
    assert ev.result.value == "error"
    assert ev.reasons[0].startswith("model not installed; run setup")
    assert ev.raw_score is None


def test_cli_binoculars_without_models_reports_error(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("Some words to analyze.", encoding="utf-8")
    code = main(["analyze", str(src), "--text-origin", "binoculars",
                 "--models-dir", str(tmp_path / "no-models")])
    assert code == 0
    rep = json.loads(capsys.readouterr().out)
    (origin,) = rep["segments"][0]["origin"]
    assert origin["method_id"] == "binoculars"
    assert origin["result"] == "error"


def test_cli_default_is_still_placeholder(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("Some words to analyze.", encoding="utf-8")
    assert main(["analyze", str(src)]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["segments"][0]["origin"][0]["method_id"] == "text_origin_placeholder"
