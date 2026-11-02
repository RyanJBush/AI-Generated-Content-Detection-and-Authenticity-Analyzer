"""Constructed durable attempt/recovery tests."""

import pytest

from litmus.calibration_run import append_event, writer_lock
from litmus.evaluation.journal import recover_tail, state
from litmus.scorer.calibration import CalibrationError


def event(kind, rid="a", attempt=1, data=None):
    return {
        "event": kind,
        "id": rid,
        "attempt": attempt,
        "time": "constructed",
        "binding": "bound",
        "data": data,
    }


@pytest.mark.parametrize("stage", ["intent", "access", "forward"])
def test_pending_row_only_recovery_and_completed_skip(tmp_path, stage):
    p = tmp_path / "journal.jsonl"
    append_event(p, event("intent"))
    if stage != "intent":
        append_event(p, event("access", data={"outcome": "read"}))
    done, pending, attempts = state(p, ["a", "b"], "bound", lambda *x: None)
    assert not done and pending == "a" and attempts == {"a": 1}
    append_event(p, event("intent", attempt=2))
    append_event(p, event("access", attempt=2, data={"outcome": "read"}))
    append_event(p, event("completion", attempt=2, data={"status": "failed"}))
    done, pending, attempts = state(p, ["a", "b"], "bound", lambda *x: None)
    assert (
        done == {"a": {"status": "failed"}} and pending is None and attempts["a"] == 2
    )
    append_event(p, event("intent", attempt=3))
    with pytest.raises(CalibrationError):
        state(p, ["a", "b"], "bound", lambda *x: None)


def test_lock_and_truncated_tail_preserve_and_earlier_corruption(tmp_path):
    with writer_lock(tmp_path):
        with pytest.raises(CalibrationError):
            with writer_lock(tmp_path):
                pass
    p = tmp_path / "journal.jsonl"
    append_event(p, event("intent"))
    original = p.read_bytes() + b'{"broken"'
    p.write_bytes(original)
    with pytest.raises(CalibrationError, match="truncated"):
        state(p, ["a"], "bound", lambda *x: None)
    recover_tail(p, ["a"], "bound", lambda *x: None)
    assert (tmp_path / "journal.jsonl.damaged").read_bytes() == original
    assert state(p, ["a"], "bound", lambda *x: None)[1] == "a"
    p.write_bytes(b"bad\npartial")
    with pytest.raises((CalibrationError, ValueError)):
        recover_tail(p, ["a"], "bound", lambda *x: None)


@pytest.mark.parametrize(
    "bad",
    [
        event("intent", "z"),
        event("intent", "b"),
        event("completion"),
        {**event("intent"), "binding": "other"},
        event("abort", data="systemic"),
    ],
)
def test_unknown_order_binding_systemic_abort_refused(tmp_path, bad):
    p = tmp_path / "journal.jsonl"
    append_event(p, bad)
    with pytest.raises(CalibrationError):
        state(p, ["a", "b"], "bound", lambda *x: None)
