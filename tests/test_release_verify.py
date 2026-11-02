"""Constructed corruption checks for the supported read-only verifier."""

import pytest

from litmus.data_prep.keys import canonical
from litmus.evaluation.run import IDENTITY
from litmus.release_verify import strict_journal
from litmus.scorer.calibration import CalibrationError, sha


def fixture_events():
    row = {k: k for k in IDENTITY}
    row.update(id="a", source_id="s", split="test", utf8_bytes=12)
    header = {"constructed": True}
    binding = sha(canonical(header))
    events = [
        {
            "event": kind,
            "id": "a",
            "attempt": 1,
            "time": "constructed",
            "binding": binding,
            "data": data,
        }
        for kind, data in (
            ("intent", {k: row[k] for k in IDENTITY}),
            (
                "access",
                {
                    "outcome": "read",
                    "raw_text_sha256": row["raw_text_sha256"],
                    "bytes": 12,
                },
            ),
            ("completion", {"status": "valid"}),
        )
    ]
    return row, header, events


def encode(events):
    return b"".join(canonical(e) + b"\n" for e in events)


def test_complete_strict_journal():
    row, header, events = fixture_events()
    calls = []
    done = strict_journal(
        encode(events), [row], header, lambda *args: calls.append(args)
    )
    assert list(done) == ["a"] and len(calls) == 1


@pytest.mark.parametrize(
    "case",
    [
        "intent",
        "hash",
        "bytes",
        "extra",
        "unknown",
        "binding",
        "duplicate",
        "order",
        "attempt",
        "tail",
        "incomplete",
        "abort",
    ],
)
def test_corruption_rejected_before_any_downstream_validation(case):
    row, header, events = fixture_events()
    if case == "intent":
        events[0]["data"]["id"] = "WRONG"
    if case == "hash":
        events[1]["data"]["raw_text_sha256"] = "WRONG"
    if case == "bytes":
        events[1]["data"]["bytes"] = -1
    if case == "extra":
        events[1]["data"]["extra"] = True
    if case == "unknown":
        events[0]["id"] = "unknown"
    if case == "binding":
        events[0]["binding"] = "wrong"
    if case == "duplicate":
        events.append(events[-1])
    if case == "order":
        events = events[1:] + events[:1]
    if case == "attempt":
        events[1]["attempt"] = 2
    if case == "incomplete":
        events = events[:2]
    if case == "abort":
        events[2]["event"] = "abort"
    data = encode(events)
    if case == "tail":
        data += b'{"partial"'
    calls = []
    with pytest.raises((CalibrationError, ValueError)):
        strict_journal(data, [row], header, lambda *args: calls.append(args))
    assert calls == []
