"""Constructed scoring and gate orchestration; no real test texts or scores."""

import contextlib
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from litmus.calibration_run import new_json, read_json
from litmus.evaluation import run
from litmus.evaluation.gate import CFG, Access
from litmus.evaluation.metrics import POLICY
from litmus.schemas import Calibration, OriginEvidence, OriginResult
from litmus.scorer.calibration import CalibrationError, sha


def constructed(tmp_path):
    blob = b"constructed text"
    row = {
        "id": "a",
        "source_id": "s",
        "split": "test",
        "role": "human",
        "attack": "none",
        "adv_source_id": "",
        "raw_text_sha256": sha(blob),
        "scored_window_sha256": "window",
        "text_blob": "texts/constructed.txt",
        "utf8_bytes": len(blob),
        "tokens_scored": 64,
        "tokens_total": 64,
        "truncated": False,
        "scored_char_range": [0, len(blob)],
    }
    path = tmp_path / "data/raid/prepared/primary" / row["text_blob"]
    path.parent.mkdir(parents=True)
    path.write_bytes(blob)
    stats = {
        "score": 1.0,
        "nll_performer": 1.0,
        "xent": 1.0,
        "n_input_tokens": 64,
        "n_target_tokens": 63,
    }
    cal = Calibration(CFG, "dev", 0.05, POLICY["threshold_c"], 298, "constructed")
    ev = OriginEvidence(
        "binoculars",
        "constructed",
        OriginResult.NO_SIGNAL,
        raw_score=1.0,
        calibration=cal,
        reasons=["not_above_calibrated_threshold"],
        details={
            **{k: stats[k] for k in run.STATS},
            "scored_window": {k: row[k] for k in run.WINDOW},
            "scoring_config_hash": CFG,
            "scoring_config": {"constructed": True},
            "execution_profile_complete": True,
            "execution_profile_failures": {},
            "calibration_artifact_sha256": "artifact",
        },
    )
    header = {
        "scoring_config_hash": CFG,
        "calibration_projection": run.asdict(cal),
        "calibration_artifact_sha256": "artifact",
    }
    return row, path, ev, header


@pytest.mark.parametrize(
    "mode", ["valid", "numerical", "unknown", "window", "raw", "profile", "validation"]
)
def test_score_single_read_identity_numerical_and_systemic_paths(
    tmp_path, monkeypatch, mode
):
    row, path, ev, header = constructed(tmp_path)
    directory = tmp_path / "out"
    directory.mkdir()
    calls = []

    def score(*args):
        calls.append(1)
        if mode == "unknown":
            raise RuntimeError("systemic")
        return ev

    if mode == "numerical":
        ev = replace(
            ev,
            result=OriginResult.ERROR,
            raw_score=None,
            reasons=["numerical_error: xent is not finite (nan)"],
        )
    if mode == "validation":
        ev = replace(
            ev,
            result=OriginResult.ERROR,
            raw_score=None,
            reasons=["numerical_error: score_ratio_mismatch"],
        )
    if mode == "profile":
        ev.details["execution_profile_complete"] = False
    if mode == "raw":
        path.write_bytes(b"changed")
    observed = {
        k: row[k] for k in ("raw_text_sha256", "scored_window_sha256", *run.WINDOW)
    }
    if mode == "window":
        observed["tokens_scored"] = 65
    monkeypatch.setattr(run, "assess", lambda *x: (observed, []))
    with Access(tmp_path, [row]) as access:
        s = {
            "pair": SimpleNamespace(tokenizer=None),
            "analyzer": SimpleNamespace(score_text=score),
            "fields": {"constructed": True},
            "check": lambda: None,
            "access": access,
        }
        if mode in ("valid", "numerical"):
            result = run.score_one(tmp_path, row, s, directory, "bound", 1, header)
            assert result["status"] == ("valid" if mode == "valid" else "failed")
            assert len(calls) == access.opens == 1
            run.validate_result(result, row, header)
            if mode == "valid":
                result["flag"] = True
                with pytest.raises(CalibrationError):
                    run.validate_result(result, row, header)
        else:
            with pytest.raises((CalibrationError, RuntimeError)):
                run.score_one(tmp_path, row, s, directory, "bound", 1, header)
            assert access.opens == 1
            assert len(calls) == (0 if mode in ("raw", "window") else 1)


@pytest.mark.parametrize("gate", ["accepted", "snapshot", "session", "synthetic"])
def test_every_preaccess_gate_failure_zero_calls(tmp_path, monkeypatch, gate):
    opened = []

    def fail(*args):
        raise CalibrationError("constructed_gate_failure")

    monkeypatch.setattr(
        run, "accepted_state", fail if gate == "accepted" else lambda *a: {}
    )
    monkeypatch.setattr(
        run, "evaluation_snapshot", fail if gate == "snapshot" else lambda *a: {}
    )

    @contextlib.contextmanager
    def fake_session(*a):
        if gate == "session":
            fail()
        yield {}

    monkeypatch.setattr(run, "session", fake_session)
    monkeypatch.setattr(run, "synthetic", fail)
    monkeypatch.setattr(run, "score_one", lambda *a: opened.append(1))
    with pytest.raises(CalibrationError):
        run.run(tmp_path, tmp_path / "out")
    assert opened == []


@pytest.mark.parametrize("bad", [None, True, float("nan"), float("inf"), "1"])
def test_invalid_numerical_values_rejected(tmp_path, bad):
    row, _, ev, header = constructed(tmp_path)
    result = {
        **run.record_identity(row),
        "scoring_config_hash": CFG,
        "status": "valid",
        "stats": {**{k: ev.details[k] for k in run.STATS}, "score": bad},
        "scored_window": ev.details["scored_window"],
        "flag": False,
        "oriented_score": -1.0,
        "reasons": ev.reasons,
        "calibration": run.asdict(ev.calibration),
        "calibration_artifact_sha256": "artifact",
    }
    with pytest.raises(CalibrationError):
        run.validate_result(result, row, header)


def test_import_isolation_and_cli_help():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import litmus.evaluation.run; "
            "assert 'torch' not in sys.modules; "
            "assert 'transformers' not in sys.modules",
        ],
        check=True,
        capture_output=True,
    )
    assert result.returncode == 0
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_r1g.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"], check=True, capture_output=True
    )
    assert b"verify-results" in result.stdout and b"calibrate" not in result.stdout


def test_policy_roundtrip(tmp_path):
    new_json(tmp_path / "p.json", POLICY)
    assert read_json(tmp_path / "p.json") == POLICY


def test_threshold_equality_unflagged_and_g_does_not_change_scorer_identity(tmp_path):
    from litmus.scorer.identity import SOURCE_FILES, source_sha256

    before = source_sha256()
    assert not any("evaluation" in p for p in SOURCE_FILES)
    row, _, ev, header = constructed(tmp_path)
    raw = -POLICY["threshold_c"]
    result = {
        **run.record_identity(row),
        "scoring_config_hash": CFG,
        "status": "valid",
        "stats": {
            **{k: ev.details[k] for k in run.STATS},
            "score": raw,
            "nll_performer": raw,
        },
        "scored_window": ev.details["scored_window"],
        "flag": False,
        "oriented_score": -raw,
        "reasons": ev.reasons,
        "calibration": run.asdict(ev.calibration),
        "calibration_artifact_sha256": "artifact",
    }
    run.validate_result(result, row, header)
    result["flag"] = True
    with pytest.raises(CalibrationError):
        run.validate_result(result, row, header)
    assert before == source_sha256()
