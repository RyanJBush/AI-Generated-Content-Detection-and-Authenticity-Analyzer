"""App smoke tests (SPEC §8.3): build the interface without loading models; no flag without valid calibration."""
import importlib.util
import json
from pathlib import Path

import gradio as gr
import pytest
from fakes import fake_pair

from litmus.cli import Analyzer
from litmus.identity import compute_identity

APP_PATH = Path(__file__).resolve().parents[1] / "app" / "app.py"
TEXT = "Perhaps the committee met. " + " ".join(["word"] * 70) + " Studies show that it might rain. It might rain."


@pytest.fixture(scope="module")
def app():
    spec = importlib.util.spec_from_file_location("litmus_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_load(calls):
    def load(pair, device, dtype):
        calls.append((pair, device, dtype))
        return fake_pair()
    return load


def test_build_app_does_not_load_models(app):
    calls = []
    demo = app.build_app(app.lazy_report_fn(load=fake_load(calls)))
    assert isinstance(demo, gr.Blocks)
    assert calls == []


def test_models_load_once_on_first_analysis(app, tmp_path):
    calls = []
    report_fn = app.lazy_report_fn(load=fake_load(calls))
    report_fn(TEXT)
    report_fn(TEXT)
    assert len(calls) == 1


def test_no_flag_shown_without_calibration(app, tmp_path):
    analyzer = Analyzer(fake_pair(), calibration_dir=tmp_path)
    summary, _segments, raw = app.run_analysis(TEXT, analyzer.report)
    report = json.loads(raw)
    assert report["binoculars"]["flag"] == "no_calibration"
    assert "No flag shown" in summary and "**Flag:**" not in summary
    assert "not a probability" in summary and report["disclaimer"] in summary


def test_no_flag_shown_when_calibration_fingerprint_mismatches(app, tmp_path):
    identity = compute_identity(fake_pair())
    data = {
        "format_version": 1, "scoring_config_hash": identity["scoring_config_hash"],
        "scoring_identity_hash": "f" * 64, "execution_profile_hash": identity["execution_profile_hash"],
        "detectors": {"binoculars": {"direction": "lower_is_machine", "thresholds": {
            "fpr_0.01": {"threshold": 5.0}, "fpr_0.05": {"threshold": 6.0}}}},
    }
    (tmp_path / f"{identity['scoring_config_hash']}.json").write_text(json.dumps(data), encoding="utf-8")
    summary, _, raw = app.run_analysis(TEXT, Analyzer(fake_pair(), calibration_dir=tmp_path).report)
    assert json.loads(raw)["binoculars"]["flag"] == "no_calibration"
    assert "does not match" in summary and "**Flag:**" not in summary


def test_flag_shown_with_matching_calibration(app, tmp_path):
    identity = compute_identity(fake_pair())
    data = {
        "format_version": 1, **{k: identity[k] for k in
                                ["scoring_config_hash", "scoring_identity_hash", "execution_profile_hash"]},
        "detectors": {"binoculars": {"direction": "lower_is_machine", "thresholds": {
            "fpr_0.01": {"threshold": 0.0}, "fpr_0.05": {"threshold": 0.0}}}},
    }
    (tmp_path / f"{identity['scoring_config_hash']}.json").write_text(json.dumps(data), encoding="utf-8")
    summary, _, raw = app.run_analysis(TEXT, Analyzer(fake_pair(), calibration_dir=tmp_path).report)
    assert json.loads(raw)["binoculars"]["flag"] == "not_flagged"
    assert "**Flag:** not_flagged (score did not cross the calibrated threshold" in summary


def test_highlight_segments_cover_text_and_combine_overlaps(app, tmp_path):
    report = Analyzer(fake_pair(), calibration_dir=tmp_path).report(TEXT)
    segments = app.highlight_segments(TEXT, report)
    assert "".join(s for s, _ in segments) == TEXT
    labelled = {s: label for s, label in segments if label}
    assert labelled["Perhaps"] == "hedge"
    assert labelled["Studies show"] == "phrase to inspect"
    # "might" sits inside the repeated 3-gram "it might rain".
    assert labelled["might"] == "hedge + repeated 3-gram"


def test_too_short_summary(app, tmp_path):
    summary, _, raw = app.run_analysis("Too short.", Analyzer(fake_pair(), calibration_dir=tmp_path).report)
    assert json.loads(raw)["binoculars"]["flag"] == "too_short"
    assert summary.startswith("**Not scored:**")
