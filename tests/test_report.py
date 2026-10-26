"""Model-free tests for calibration lookup, flag policy, and the report object (SPEC §3.3, §8.3)."""
import json

import pytest
from fakes import fake_pair

from litmus.calibration import CalibrationStatus, load_calibration
from litmus.identity import compute_identity
from litmus.report import DISCLAIMER, NOTE, build_report, decide_flag, report_to_json
from litmus.scoring import ScoreResult
from litmus.slop import analyze

IDENTITY = compute_identity(fake_pair())
NO_CALIBRATION = CalibrationStatus(False, "no calibration file for this scoring configuration", "calibration/x.json")
VALID = CalibrationStatus(True, "valid", "calibration/x.json", t_strict=0.8, t_primary=0.9, artifact_sha256="a" * 64)


def ok(score):
    return ScoreResult(status="ok", n_tokens=100, n_input_tokens=100, n_scored_tokens=99, truncated=False,
                       nll_performer=2.0, nll_observer=2.1, xent=2.0 / score, score=score)


TOO_SHORT = ScoreResult(status="too_short", n_tokens=10, n_input_tokens=10, n_scored_tokens=None, truncated=False)
ERROR = ScoreResult(status="error", n_tokens=100, n_input_tokens=100, n_scored_tokens=99, truncated=False,
                    error="xent must be > 0, got 0.0 for document 0")


def calibration_file(identity, **overrides):
    data = {
        "format_version": 1,
        "scoring_config_hash": identity["scoring_config_hash"],
        "scoring_identity_hash": identity["scoring_identity_hash"],
        "execution_profile_hash": identity["execution_profile_hash"],
        "pair": {"observer": "fake/observer@0", "performer": "fake/performer@0"},
        "weight_dtype": "float32",
        "dev_manifest_sha256": "0" * 64,
        "counts": {"human_rows": 10, "source_groups": 10},
        "selection_rule": "test fixture",
        "detectors": {"binoculars": {"direction": "lower_is_machine", "thresholds": {
            "fpr_0.01": {"threshold": 0.8, "achieved_dev_fpr": 0.01},
            "fpr_0.05": {"threshold": 0.9, "achieved_dev_fpr": 0.05},
        }}},
    }
    data.update(overrides)
    return data


# --- Flag policy ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("score, flag", [
    (0.7999, "flagged"), (0.8, "uncertain_abstain"), (0.8999, "uncertain_abstain"), (0.9, "not_flagged"), (1.2, "not_flagged"),
])
def test_threshold_policy(score, flag):
    assert decide_flag(ok(score), VALID) == flag


def test_no_flag_without_valid_calibration():
    assert decide_flag(ok(0.1), NO_CALIBRATION) == "no_calibration"


def test_too_short_and_error_take_precedence():
    assert decide_flag(TOO_SHORT, VALID) == "too_short"
    assert decide_flag(ERROR, VALID) is None


# --- Calibration lookup --------------------------------------------------------------------------------------


def write_calibration(tmp_path, identity, data):
    (tmp_path / f"{identity['scoring_config_hash']}.json").write_text(json.dumps(data), encoding="utf-8")


def test_missing_calibration(tmp_path):
    status = load_calibration(IDENTITY, tmp_path)
    assert not status.valid and status.reason == "no calibration file for this scoring configuration"


def test_valid_calibration(tmp_path):
    write_calibration(tmp_path, IDENTITY, calibration_file(IDENTITY))
    status = load_calibration(IDENTITY, tmp_path)
    assert status.valid and (status.t_strict, status.t_primary) == (0.8, 0.9)
    assert len(status.artifact_sha256) == 64


@pytest.mark.parametrize("overrides, reason", [
    ({"format_version": 2}, "format_version"),
    ({"scoring_identity_hash": "f" * 64}, "scoring_identity_hash"),
    ({"execution_profile_hash": "f" * 64}, "execution_profile_hash"),
    ({"scoring_config_hash": "f" * 64}, "scoring_config_hash"),
    ({"detectors": {}}, "lacks binoculars"),
    ({"detectors": {"binoculars": {"direction": "higher_is_machine", "thresholds": {
        "fpr_0.01": {"threshold": 0.8}, "fpr_0.05": {"threshold": 0.9}}}}}, "direction"),
    ({"detectors": {"binoculars": {"direction": "lower_is_machine", "thresholds": {
        "fpr_0.01": {"threshold": 0.95}, "fpr_0.05": {"threshold": 0.9}}}}}, "t_strict must not exceed"),
    ({"detectors": {"binoculars": {"direction": "lower_is_machine", "thresholds": {
        "fpr_0.01": {"threshold": None}, "fpr_0.05": {"threshold": 0.9}}}}}, "finite"),
])
def test_invalid_calibration_is_rejected(tmp_path, overrides, reason):
    write_calibration(tmp_path, IDENTITY, calibration_file(IDENTITY, **overrides))
    status = load_calibration(IDENTITY, tmp_path)
    assert not status.valid and reason in status.reason


def test_calibration_for_other_profile_is_not_used(tmp_path):
    # A valid file for a different scoring_config_hash (e.g. another dtype) is not picked up.
    other = {**IDENTITY, "scoring_config_hash": "e" * 64}
    write_calibration(tmp_path, other, calibration_file(other))
    assert not load_calibration(IDENTITY, tmp_path).valid


def test_unparseable_calibration(tmp_path):
    (tmp_path / f"{IDENTITY['scoring_config_hash']}.json").write_text("{", encoding="utf-8")
    status = load_calibration(IDENTITY, tmp_path)
    assert not status.valid and "not valid JSON" in status.reason


# --- Report object -------------------------------------------------------------------------------------------

TEXT = "Studies show that it might rain. " * 5


def test_report_without_calibration_has_raw_score_note_and_disclaimer():
    report = build_report(TEXT, ok(0.85), analyze(TEXT), IDENTITY, NO_CALIBRATION)
    b = report["binoculars"]
    assert b["flag"] == "no_calibration" and b["calibration"] is None
    assert b["score"] == 0.85 and b["baselines"]["nll_observer"] == 2.1
    assert b["note"] == NOTE and "not a probability" in NOTE
    assert report["disclaimer"] == DISCLAIMER
    assert b["calibration_status"] == {"valid": False, "reason": NO_CALIBRATION.reason, "path": NO_CALIBRATION.path}
    assert report["models"] == {"observer": "fake/observer@0", "performer": "fake/performer@0",
                                "tokenizer_sha256": "0" * 64, "weight_dtype": "float32"}
    for key in ["scoring_config_hash", "scoring_identity_hash", "execution_profile_hash"]:
        assert report[key] == IDENTITY[key]
    assert report["version"] == "0.3.2"


def test_report_with_valid_calibration():
    report = build_report(TEXT, ok(0.85), analyze(TEXT), IDENTITY, VALID)
    b = report["binoculars"]
    assert b["flag"] == "uncertain_abstain"
    assert b["calibration"] == {
        "artifact_sha256": "a" * 64, "scoring_config_hash": IDENTITY["scoring_config_hash"],
        "scoring_identity_hash": IDENTITY["scoring_identity_hash"],
        "execution_profile_hash": IDENTITY["execution_profile_hash"],
        "t_strict": 0.8, "t_primary": 0.9, "source": "clean human dev rows",
    }


def test_not_flagged_wording_never_claims_human():
    report = build_report(TEXT, ok(1.0), analyze(TEXT), IDENTITY, VALID)
    assert report["binoculars"]["flag_text"] == "score did not cross the calibrated threshold"
    assert "human" not in report["binoculars"]["flag_text"]


def test_too_short_and_error_reports_use_null_not_zero():
    short = build_report("Too short.", TOO_SHORT, analyze("Too short."), IDENTITY, VALID)
    assert short["binoculars"]["flag"] == "too_short"
    assert short["n_scored_tokens"] is None
    for key in ["nll_performer", "xent", "score"]:
        assert short["binoculars"][key] is None
    assert short["binoculars"]["baselines"]["nll_observer"] is None
    error = build_report(TEXT, ERROR, analyze(TEXT), IDENTITY, VALID)
    assert error["binoculars"]["flag"] is None and error["binoculars"]["score"] is None
    assert error["binoculars"]["error"].startswith("xent must be > 0")


def test_report_json_round_trip_preserves_unicode_and_rejects_nan():
    text = "Café 🌍 studies show résumé. " * 3
    report = build_report(text, ok(0.95), analyze(text), IDENTITY, NO_CALIBRATION)
    encoded = report_to_json(report)
    assert "café studies show" in encoded  # repeated 3-gram, written as UTF-8 rather than \u escapes
    assert json.loads(encoded) == report
    bad = build_report(text, ok(0.95), analyze(text), IDENTITY, NO_CALIBRATION)
    bad["binoculars"]["score"] = float("nan")
    with pytest.raises(ValueError):
        report_to_json(bad)


def test_report_rejects_spans_outside_text():
    slop = analyze(TEXT)
    slop["features"]["hedges"]["spans"].append([0, len(TEXT) + 1])
    with pytest.raises(ValueError):
        build_report(TEXT, ok(0.9), slop, IDENTITY, NO_CALIBRATION)
