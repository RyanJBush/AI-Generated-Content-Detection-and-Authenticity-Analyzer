"""Constructed scores/artifacts only; never real calibration evidence."""

import json

import pytest
from test_scoring_identity import PROFILE, fields

from litmus.scorer.calibration import (
    CalibrationError,
    create_artifact,
    find_calibration,
    orient,
    select_threshold,
    validate_artifact,
)


def artifact(scores=None):
    return create_artifact(
        scores if scores is not None else [float(i) / 100 for i in range(200)],
        fields(),
        {
            "dev_set_id": "1" * 64,
            "prepared_manifest_sha256": "2" * 64,
            "reconciliation_sha256": "3" * 64,
            "scores_sha256": "4" * 64,
            "source_run_id": "constructed",
            "failed_negatives": 0,
        },
        "2026-11-01T00:00:00+00:00",
    )


def test_exact_threshold_oracle_ties_and_orientation():
    for n in (200, 201, 298):
        for scores in (
            [float(i) for i in range(n)],
            [1.0] * n,
            [float(i // 7) for i in range(n)],
        ):
            expected = min(
                c for c in set(scores) if 20 * sum(r > c for r in scores) <= n
            )
            result = select_threshold(scores)
            assert result["threshold_c"] == expected
            assert result == select_threshold(list(reversed(scores)))
            assert result["above"] == sum(r > expected for r in scores)
            assert result["ties"] == scores.count(expected)
    assert select_threshold(list(map(float, range(200))))["threshold_c"] == 189
    assert select_threshold(list(map(float, range(298))))["threshold_c"] == 283
    assert orient(0.8, "lower_means_more_machine") == -0.8
    assert orient(0.8, "higher_means_more_machine") == 0.8


@pytest.mark.parametrize(
    "values,alpha",
    [
        ([], 0.05),
        ([1.0] * 199, 0.05),
        ([1.0] * 1000, 0.01),
        ([float("nan")] * 200, 0.05),
        ([float("inf")] * 200, 0.05),
        ([True] * 200, 0.05),
    ],
)
def test_invalid_threshold_inputs(values, alpha):
    with pytest.raises(CalibrationError):
        select_threshold(values, alpha)


def test_artifact_roundtrip_and_strict_lookup(tmp_path):
    value = artifact()
    assert validate_artifact(json.loads(json.dumps(value))) == value["payload"]
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(value))
    h = value["payload"]["scoring_config_hash"]
    assert find_calibration(h, tmp_path) == value
    assert find_calibration("f" * 64, tmp_path) is None
    (tmp_path / "duplicate.json").write_text(json.dumps(value))
    with pytest.raises(CalibrationError, match="ambiguous"):
        find_calibration(h, tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        "threshold_c",
        "n_dev_negatives",
        "alpha",
        "score_direction",
        "scoring_config_hash",
        "extra",
        "freeze_sha256",
    ],
)
def test_artifact_tampering_rejected(change):
    value = artifact()
    value["payload"][change] = True
    with pytest.raises(CalibrationError):
        validate_artifact(value)


def test_artifact_numerics_and_schema_are_not_just_self_hashes():
    from litmus.scorer.calibration import envelope

    value = artifact()
    for key, bad in (
        ("threshold_c", float("inf")),
        ("n_dev_negatives", 199),
        ("alpha", 0.01),
        ("above", 11),
        ("comparison", ">="),
    ):
        payload = dict(value["payload"], **{key: bad})
        with pytest.raises(CalibrationError):
            validate_artifact(
                envelope(payload, "artifact_sha256", created=value["created"])
            )


def test_malformed_duplicate_keys_fail_closed(tmp_path):
    from litmus.scorer.calibration import strict_json

    for content in ('{"x":1,"x":2}', '{"x":NaN}', "[]", "{"):
        (tmp_path / "bad.json").write_text(content)
        with pytest.raises(CalibrationError):
            find_calibration("a" * 64, tmp_path)
    with pytest.raises(CalibrationError):
        strict_json('{"x":Infinity}')


def test_application_strict_tie_and_report_roundtrip(tmp_path):
    from litmus.schemas import OriginEvidence, from_json, to_json
    from litmus.scorer.analyzer import evidence_from_score

    value = artifact([1.0] * 200)
    (tmp_path / "cal.json").write_text(json.dumps(value))
    for raw, result in ((0.5, "supports_ai"), (1.0, "no_signal"), (1.5, "no_signal")):
        stats = {
            "score": raw,
            "nll_performer": raw * 2,
            "xent": 2.0,
            "n_input_tokens": 100,
            "n_target_tokens": 99,
        }
        window = {
            "tokens_total": 100,
            "tokens_scored": 100,
            "truncated": False,
            "scored_char_range": [0, 400],
        }
        ev = evidence_from_score(
            stats,
            window,
            PROFILE,
            fields(),
            value["payload"]["scoring_config_hash"],
            151665,
            151936,
            tmp_path,
        )
        assert ev.result.value == result
        assert ev.calibration.threshold_c == -1.0
        assert to_json(from_json(OriginEvidence, to_json(ev))) == to_json(ev)


def test_cli_constructed_calibration_projection_and_creation_bypass(
    tmp_path, monkeypatch, capsys
):
    from litmus.cli import main
    from litmus.scorer.analyzer import BinocularsAnalyzer, evidence_from_score

    value = artifact([1.0] * 200)
    (tmp_path / "cal.json").write_text(json.dumps(value))
    stats = {
        "score": 0.5,
        "nll_performer": 1.0,
        "xent": 2.0,
        "n_input_tokens": 100,
        "n_target_tokens": 99,
    }
    window = {
        "tokens_total": 100,
        "tokens_scored": 100,
        "truncated": False,
        "scored_char_range": [0, 100],
    }
    ev = evidence_from_score(
        stats,
        window,
        PROFILE,
        fields(),
        value["payload"]["scoring_config_hash"],
        151665,
        151936,
        tmp_path,
    )
    monkeypatch.setattr(BinocularsAnalyzer, "__call__", lambda self, text: ev)
    text = tmp_path / "constructed.txt"
    text.write_text("constructed report probe " * 10)
    assert main(["analyze", str(text), "--text-origin", "binoculars"]) == 0
    report = json.loads(capsys.readouterr().out)
    origin = report["segments"][0]["origin"][0]
    assert origin["result"] == "supports_ai"
    assert origin["calibration"]["n_dev_negatives"] == 200
    assert origin["calibration"]["threshold_c"] == -1.0
    assert "uncalibrated in R1-B1" not in str(report["limitations"])
    (tmp_path / "cal.json").write_text("{broken")
    bypass = evidence_from_score(
        stats,
        window,
        PROFILE,
        fields(),
        value["payload"]["scoring_config_hash"],
        151665,
        151936,
        tmp_path,
        apply_calibration=False,
    )
    assert (
        bypass.reasons == ["calibration_disabled_for_creation"]
        and bypass.calibration is None
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, -1.0])
def test_bad_scores_are_errors_not_flags(tmp_path, bad):
    from litmus.scorer.analyzer import evidence_from_score

    stats = {
        "score": bad,
        "nll_performer": 1.0,
        "xent": 2.0,
        "n_input_tokens": 100,
        "n_target_tokens": 99,
    }
    ev = evidence_from_score(
        stats, {}, PROFILE, fields(), "f" * 64, 151665, 151936, tmp_path
    )
    assert (
        ev.result.value == "error" and ev.raw_score is None and ev.calibration is None
    )


def test_single_validated_lookup_and_runtime_profile_consistency(monkeypatch, tmp_path):
    from litmus.scorer import analyzer

    value = artifact([1.0] * 200)
    calls = []
    monkeypatch.setattr(
        analyzer, "find_calibration", lambda *args: (calls.append(args), value)[1]
    )
    stats = {
        "score": 0.5,
        "nll_performer": 1.0,
        "xent": 2.0,
        "n_input_tokens": 100,
        "n_target_tokens": 99,
    }
    window = {
        "tokens_total": 100,
        "tokens_scored": 100,
        "truncated": False,
        "scored_char_range": [0, 100],
    }
    ev = analyzer.evidence_from_score(
        stats,
        window,
        PROFILE,
        fields(),
        value["payload"]["scoring_config_hash"],
        151665,
        151936,
        tmp_path,
    )
    assert ev.result.value == "supports_ai" and len(calls) == 1
    changed = dict(PROFILE, nvidia_driver_version="2.3")
    bad = analyzer.evidence_from_score(
        stats,
        window,
        changed,
        fields(),
        value["payload"]["scoring_config_hash"],
        151665,
        151936,
        tmp_path,
    )
    assert bad.result.value == "inconclusive" and bad.reasons == ["calibration_invalid"]
    assert bad.details["calibration_error"] == "calibration_runtime_profile_mismatch"


def test_invalid_artifact_has_actionable_evidence_diagnostic(tmp_path):
    from litmus.scorer.analyzer import evidence_from_score

    (tmp_path / "broken.json").write_text("{broken")
    stats = {
        "score": 0.5,
        "nll_performer": 1.0,
        "xent": 2.0,
        "n_input_tokens": 100,
        "n_target_tokens": 99,
    }
    window = {
        "tokens_total": 100,
        "tokens_scored": 100,
        "truncated": False,
        "scored_char_range": [0, 100],
    }
    ev = evidence_from_score(
        stats, window, PROFILE, fields(), "f" * 64, 151665, 151936, tmp_path
    )
    assert ev.reasons == ["calibration_invalid"] and ev.calibration is None
    assert "broken.json" in ev.details["calibration_error"]
