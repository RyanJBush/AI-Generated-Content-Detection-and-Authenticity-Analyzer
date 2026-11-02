"""Authoritative fsynced access/attempt/completion log with explicit tail recovery."""

from litmus.calibration_run import new_bytes
from litmus.scorer.calibration import require, strict_json


def parse(data, ids, binding, validate):
    require(
        not data or data.endswith(b"\n"),
        "journal_truncated_tail; explicit recovery required",
    )
    done, attempts, pending, accessed = {}, {}, None, False
    for line in data.splitlines():
        e = strict_json(line)
        require(
            set(e) == {"event", "id", "attempt", "time", "binding", "data"},
            "journal_fields",
        )
        rid, kind = e["id"], e["event"]
        require(e["binding"] == binding and rid in ids, "journal_binding_or_unknown")
        require(
            len(done) < len(ids) and rid == ids[len(done)] and rid not in done,
            "duplicate_terminal_or_gap",
        )
        require(kind != "abort", "systemic_abort; new decision required")
        if kind == "intent":
            require(
                type(e["attempt"]) is int and e["attempt"] == attempts.get(rid, 0) + 1,
                "attempt_sequence",
            )
            attempts[rid] = e["attempt"]
            pending, accessed = rid, False
        else:
            require(
                pending == rid and e["attempt"] == attempts[rid],
                "event_without_attempt",
            )
            if kind == "access":
                require(
                    not accessed and e["data"]["outcome"] == "read",
                    "duplicate_or_failed_access",
                )
                accessed = True
            else:
                require(kind == "completion" and accessed, "completion_without_read")
                validate(e["data"], rid)
                done[rid], pending, accessed = e["data"], None, False
    return done, pending, attempts


def state(path, ids, binding, validate):
    return parse(path.read_bytes() if path.exists() else b"", ids, binding, validate)


def recover_tail(path, ids, binding, validate):
    original = path.read_bytes()
    require(not original.endswith(b"\n"), "no_truncated_tail")
    prefix = original[: original.rfind(b"\n") + 1]
    parse(prefix, ids, binding, validate)
    new_bytes(path.with_name(path.name + ".damaged"), original)
    # Only an explicit operation may truncate, after full original preservation.
    import os

    with path.open("wb") as stream:
        stream.write(prefix)
        stream.flush()
        os.fsync(stream.fileno())
