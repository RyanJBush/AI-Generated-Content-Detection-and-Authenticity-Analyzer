"""G0–G5 orchestration. No held-out performance is emitted before completion."""

import argparse
import platform
import re
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from litmus.calibration_run import (
    append_event,
    new_bytes,
    new_json,
    now,
    read_json,
    writer_lock,
)
from litmus.data_prep.acquisition import file_hash
from litmus.data_prep.keys import canonical
from litmus.data_prep.text import assess
from litmus.evaluation.gate import (
    ACCEPTED,
    ARTIFACT,
    CFG,
    FREEZE,
    G_FILES,
    MANIFEST,
    RECON,
    TEST,
    accepted_state,
    check_hashes,
    evaluation_snapshot,
    session,
)
from litmus.evaluation.journal import recover_tail, state
from litmus.evaluation.metrics import POLICY, assemble, draws_for
from litmus.scorer.calibration import (
    require,
    sha,
    strict_json,
    validate_score_statistics,
)

IDENTITY = (
    "id",
    "source_id",
    "split",
    "role",
    "attack",
    "adv_source_id",
    "raw_text_sha256",
    "scored_window_sha256",
)
WINDOW = ("tokens_total", "tokens_scored", "truncated", "scored_char_range")
STATS = ("nll_performer", "xent", "n_input_tokens", "n_target_tokens")


def record_identity(row):
    return {k: row[k] for k in IDENTITY}


def validate_result(result, row, header):
    require(
        set(result)
        == set(IDENTITY)
        | {
            "scoring_config_hash",
            "status",
            "stats",
            "scored_window",
            "flag",
            "oriented_score",
            "reasons",
            "calibration",
            "calibration_artifact_sha256",
        },
        "result_fields",
    )
    require(
        all(result[k] == row[k] for k in IDENTITY) and result["split"] == "test",
        "result_identity",
    )
    require(
        result["scoring_config_hash"] == CFG == header["scoring_config_hash"],
        "result_configuration",
    )
    require(result["scored_window"] == {k: row[k] for k in WINDOW}, "result_window")
    if result["status"] == "valid":
        validate_score_statistics(result["stats"])
        score = result["stats"]["score"]
        require(
            result["stats"]["n_input_tokens"] == row["tokens_scored"],
            "result_token_count",
        )
        require(
            type(result["flag"]) is bool
            and result["flag"] == (-score > POLICY["threshold_c"])
            and result["oriented_score"] == -score,
            "result_orientation_or_flag",
        )
        require(
            result["calibration"] == header["calibration_projection"]
            and result["calibration_artifact_sha256"]
            == header["calibration_artifact_sha256"],
            "result_calibration",
        )
        require(
            result["reasons"]
            == [
                "above_calibrated_threshold"
                if result["flag"]
                else "not_above_calibrated_threshold"
            ],
            "result_reason",
        )
    else:
        require(
            result["status"] == "failed"
            and all(
                result[k] is None
                for k in (
                    "stats",
                    "flag",
                    "oriented_score",
                    "calibration",
                    "calibration_artifact_sha256",
                )
            ),
            "invalid_failure",
        )
        require(
            len(result["reasons"]) == 1 and numerical_failure(result["reasons"][0]),
            "unknown_failure",
        )


def numerical_failure(reason):
    # Only the frozen statistic producer's explicitly numerical errors are row failures.
    # An error in the second statistics-validation layer is systemic, not accepted here.
    return (
        isinstance(reason, str)
        and re.fullmatch(
            r"numerical_error: (nll_performer|xent|score) "
            r"(is not finite \([^\n]+\)|must be (>= 0|> 0), got [^\n]+)",
            reason,
        )
        is not None
    )


def synthetic(repo, s):
    previous = read_json(repo / "eval/results/r1f/preflight_a.json")
    path = repo / "eval/inputs/r1b2/len512_00.txt"
    require(file_hash(path) == previous["synthetic_input_sha256"], "synthetic_identity")
    s["check"]()
    ev = s["analyzer"].score_text(s["pair"], path.read_text(encoding="utf-8"))
    s["check"]()
    require(
        ev.raw_score is not None and ev.calibration is not None, "synthetic_calibration"
    )
    stats = {k: ev.details[k] for k in STATS} | {"score": ev.raw_score}
    validate_score_statistics(stats)
    result = {"stats": stats, "scored_window": ev.details["scored_window"]}
    require(result == previous["synthetic_result"], "synthetic_repeat_mismatch")
    return result, asdict(ev.calibration)


def make_header(repo, accepted, snapshot, s, calibration):
    return {
        "schema": "r1g-test-run-v1",
        "created": now(),
        "accepted_freeze_commit": ACCEPTED,
        "frozen_implementation_commit": accepted["freeze"]["payload"][
            "implementation_commit"
        ],
        "freeze_file_sha256": file_hash(repo / FREEZE),
        "freeze_payload_sha256": accepted["freeze"]["freeze_sha256"],
        "calibration_file_sha256": file_hash(repo / ARTIFACT),
        "calibration_artifact_sha256": accepted["artifact"]["artifact_sha256"],
        "calibration_projection": calibration,
        "scoring_config": s["fields"],
        "scoring_config_hash": CFG,
        "prepared_manifest_sha256": MANIFEST,
        "test_projection_sha256": TEST,
        "source_version": accepted["source_version"],
        "reconciliation_sha256": file_hash(repo / RECON),
        "historical_transfer_compliance_proven": False,
        "models_manifest_sha256": s["assets"],
        "rows": 3361,
        "groups": 675,
        "policy": POLICY,
        **snapshot,
    }


def validate_header(repo, accepted, header):
    from litmus.schemas import Calibration

    p = accepted["calibration"]
    projection = asdict(
        Calibration(
            CFG,
            p["dev_set_id"],
            p["alpha"],
            p["threshold_c"],
            p["n_dev_negatives"],
            accepted["artifact"]["created"],
        )
    )
    snapshot = {
        k: header[k]
        for k in ("evaluation_commit", "evaluation_sources_sha256", "policy_sha256")
    }
    s = {
        "fields": p["scoring_config"],
        "assets": read_json(repo / "eval/results/r1f/preflight_a.json")[
            "models_manifest_sha256"
        ],
    }
    expected = make_header(repo, accepted, snapshot, s, projection)
    expected["created"] = header["created"]
    require(header == expected, "header_binding_mismatch")
    require(snapshot["policy_sha256"] == sha(canonical(POLICY)), "header_policy_digest")


def event(directory, binding, row, attempt, kind, data):
    append_event(
        directory / "journal.jsonl",
        {
            "event": kind,
            "id": row["id"],
            "attempt": attempt,
            "time": now(),
            "binding": binding,
            "data": data,
        },
    )


def score_one(repo, row, s, directory, binding, attempt, header):
    s["check"]()
    event(directory, binding, row, attempt, "intent", record_identity(row))
    s["access"].authorize(row, durable=True)
    data = (repo / "data/raid/prepared/primary" / row["text_blob"]).read_bytes()
    event(
        directory,
        binding,
        row,
        attempt,
        "access",
        {"outcome": "read", "raw_text_sha256": sha(data), "bytes": len(data)},
    )
    require(sha(data) == row["raw_text_sha256"], "raw_blob_hash_mismatch")
    text = data.decode("utf-8", errors="strict")
    observed, errors = assess(text, s["pair"].tokenizer)
    require(
        not errors and all(row.get(k) == v for k, v in observed.items()),
        "prepared_window_identity",
    )
    ev = s["analyzer"].score_text(s["pair"], text)
    s["check"]()
    base = {
        **record_identity(row),
        "scoring_config_hash": CFG,
        "scored_window": {k: row[k] for k in WINDOW},
    }
    require(ev.details.get("scored_window") == base["scored_window"], "scorer_window")
    if (
        ev.result.value == "error"
        and ev.raw_score is None
        and len(ev.reasons) == 1
        and numerical_failure(ev.reasons[0])
    ):
        result = {
            **base,
            "status": "failed",
            "stats": None,
            "flag": None,
            "oriented_score": None,
            "reasons": ev.reasons,
            "calibration": None,
            "calibration_artifact_sha256": None,
        }
    else:
        require(
            ev.details.get("scoring_config_hash") == CFG
            and ev.details.get("scoring_config") == s["fields"]
            and ev.details.get("execution_profile_complete") is True
            and not ev.details.get("execution_profile_failures"),
            "scorer_identity_or_profile",
        )
        require(
            ev.raw_score is not None
            and ev.result.value in ("supports_ai", "no_signal")
            and ev.calibration is not None,
            "scorer_systemic_failure",
        )
        require(
            ev.details.get("scored_window") == base["scored_window"], "scorer_window"
        )
        stats = {k: ev.details[k] for k in STATS} | {"score": ev.raw_score}
        result = {
            **base,
            "status": "valid",
            "stats": stats,
            "flag": ev.result.value == "supports_ai",
            "oriented_score": -ev.raw_score,
            "reasons": ev.reasons,
            "calibration": asdict(ev.calibration),
            "calibration_artifact_sha256": ev.details.get(
                "calibration_artifact_sha256"
            ),
        }
    validate_result(result, row, header)
    event(directory, binding, row, attempt, "completion", result)
    return result


def persist(path, data):
    if path.exists():
        require(path.read_bytes() == data, "existing_output_changed:" + path.name)
    else:
        new_bytes(path, data)


def json_persist(path, value):
    persist(path, canonical(value) + b"\n")


def run(repo, directory, preflight_only=False):
    started, cpu = time.monotonic(), time.process_time()
    accepted, snapshot = accepted_state(repo), evaluation_snapshot(repo)
    with writer_lock(directory):
        with session(repo, accepted, snapshot) as s:
            result, calibration = synthetic(repo, s)
            header = make_header(repo, accepted, snapshot, s, calibration)
            if preflight_only:
                new_json(
                    directory / "preflight.json",
                    {
                        "status": "PASS",
                        "created": now(),
                        "header": header,
                        "synthetic": result,
                        "test_opens": s["access"].opens,
                    },
                )
            else:
                if (directory / "header.json").exists():
                    old = read_json(directory / "header.json")
                    require(
                        {k: v for k, v in old.items() if k != "created"}
                        == {k: v for k, v in header.items() if k != "created"},
                        "resume_header_mismatch",
                    )
                    header = old
                else:
                    new_json(directory / "header.json", header)
                persist(directory / "test_input.jsonl", accepted["projection"])
                json_persist(directory / "policy.json", POLICY)
                binding = sha(canonical(header))
                rows = accepted["rows"]
                by_id = {r["id"]: r for r in rows}

                def validate(value, rid):
                    validate_result(value, by_id[rid], header)

                done, pending, attempts = state(
                    directory / "journal.jsonl", list(by_id), binding, validate
                )
                for row in rows:
                    if row["id"] in done:
                        continue
                    attempt = attempts.get(row["id"], 0) + 1
                    try:
                        done[row["id"]] = score_one(
                            repo, row, s, directory, binding, attempt, header
                        )
                    except Exception as error:
                        event(
                            directory,
                            binding,
                            row,
                            attempt,
                            "abort",
                            {"type": type(error).__name__, "reason": str(error)},
                        )
                        raise
                    if len(done) % 100 == 0 or len(done) == len(rows):
                        failed = sum(v["status"] == "failed" for v in done.values())
                        print(
                            f"terminal={len(done)}/{len(rows)} failed={failed}",
                            flush=True,
                        )
                s["check"]()
        accepted_state(repo)
        telemetry = {
            **s["telemetry"],
            "wall_seconds": time.monotonic() - started,
            "process_cpu_seconds": time.process_time() - cpu,
            "created": now(),
            "operation": "preflight" if preflight_only else "score",
        }
        new_json(
            directory
            / ("preflight_execution.json" if preflight_only else "execution.json"),
            telemetry,
        )
    if not preflight_only:
        verify_saved(repo, directory, write=True)


def verify_saved(repo, directory, write=False):
    accepted = accepted_state(repo)
    header = read_json(directory / "header.json")
    validate_header(repo, accepted, header)
    require(
        header["accepted_freeze_commit"] == ACCEPTED
        and header["freeze_file_sha256"] == file_hash(repo / FREEZE)
        and header["calibration_file_sha256"] == file_hash(repo / ARTIFACT),
        "header_freeze",
    )
    require(
        header["scoring_config"] == accepted["calibration"]["scoring_config"]
        and header["scoring_config_hash"] == CFG
        and header["policy"] == POLICY
        and header["policy_sha256"] == sha(canonical(POLICY)),
        "header_policy_or_config",
    )
    require(
        header["test_projection_sha256"] == TEST
        and (directory / "test_input.jsonl").read_bytes() == accepted["projection"],
        "header_test_projection",
    )
    require(header["evaluation_sources_sha256"].keys() == set(G_FILES), "g_file_list")
    check_hashes(repo, header["evaluation_sources_sha256"])
    from litmus.calibration_run import git

    for path, digest in header["evaluation_sources_sha256"].items():
        require(
            sha(git(repo, "show", header["evaluation_commit"] + ":" + path)) == digest,
            "g_commit_identity",
        )
    rows = accepted["rows"]
    by_id = {r["id"]: r for r in rows}
    binding = sha(canonical(header))

    def validate(result, rid):
        validate_result(result, by_id[rid], header)

    done, pending, attempts = state(
        directory / "journal.jsonl", list(by_id), binding, validate
    )
    require(
        len(done) == len(rows) and pending is None, "incomplete_test_pass; no metrics"
    )
    events = [
        strict_json(line)
        for line in (directory / "journal.jsonl").read_bytes().splitlines()
    ]
    for e in events:
        row = by_id[e["id"]]
        if e["event"] == "intent":
            require(e["data"] == record_identity(row), "intent_identity")
        if e["event"] == "access":
            require(
                e["data"]
                == {
                    "outcome": "read",
                    "raw_text_sha256": row["raw_text_sha256"],
                    "bytes": row["utf8_bytes"],
                },
                "access_identity",
            )
    scores = list(done.values())
    blobs = {
        "scores.jsonl": b"".join(canonical(s) + b"\n" for s in scores),
        "failures.jsonl": b"".join(
            canonical(s) + b"\n" for s in scores if s["status"] == "failed"
        ),
        "access.jsonl": b"".join(
            canonical(e) + b"\n" for e in events if e["event"] in ("intent", "access")
        ),
    }
    counts = {
        "requested": len(rows),
        "terminal": len(scores),
        "valid": sum(s["status"] == "valid" for s in scores),
        "failed": sum(s["status"] == "failed" for s in scores),
        "pending": 0,
        "not_attempted": 0,
        "groups": len({r["source_id"] for r in rows}),
        "attempts": sum(attempts.values()),
        "successful_reads": sum(e["event"] == "access" for e in events),
        "by": {},
    }
    for dim in ("role", "domain", "model", "attack"):
        buckets = {}
        for row in rows:
            label = str(row[dim])
            bucket = buckets.setdefault(label, Counter())
            bucket["requested"] += 1
            bucket[done[row["id"]]["status"]] += 1
        counts["by"][dim] = {
            k: {
                "requested": v["requested"],
                "valid": v["valid"],
                "failed": v["failed"],
                "pending": 0,
                "not_attempted": 0,
            }
            for k, v in sorted(buckets.items())
        }
    for name, data in blobs.items():
        if write:
            persist(directory / name, data)
        else:
            require(
                (directory / name).read_bytes() == data,
                "derived_ledger_changed:" + name,
            )
    if write:
        json_persist(directory / "counts.json", counts)
    else:
        require(read_json(directory / "counts.json") == counts, "counts_changed")
    verification = {
        "status": "PASS",
        "counts": counts,
        "binding": binding,
        "journal_sha256": file_hash(directory / "journal.jsonl"),
        "files_sha256": {name: sha(data) for name, data in blobs.items()},
        "no_test_blob_reads_in_verification": True,
        "historical_transfer_compliance_proven": False,
    }
    if write:
        json_persist(directory / "verification.json", verification)
    else:
        require(
            read_json(directory / "verification.json") == verification,
            "verification_changed",
        )
    return rows, scores, header


def metrics(repo, directory, reference=False):
    rows, scores, header = verify_saved(repo, directory)
    groups = sorted({r["source_id"] for r in rows})
    draws = draws_for(groups)
    group_record = {
        "groups": groups,
        "ordered_group_sha256": sha(canonical(groups)),
        "python_version": platform.python_version(),
        "policy_sha256": header["policy_sha256"],
        "seed": POLICY["seed"],
        "tag": POLICY["tag"],
    }
    draw_bytes = b"".join(canonical(v) + b"\n" for v in draws)
    if reference:
        require(
            read_json(directory / "bootstrap_groups.json") == group_record
            and (directory / "bootstrap_draws.jsonl").read_bytes() == draw_bytes,
            "saved_draws_identity",
        )
        # The reference formula consumes the persisted scores and draws.
        draws = [
            __import__("json").loads(line)
            for line in (directory / "bootstrap_draws.jsonl").read_bytes().splitlines()
        ]
    else:
        json_persist(directory / "bootstrap_groups.json", group_record)
        persist(directory / "bootstrap_draws.jsonl", draw_bytes)
    started, cpu = time.monotonic(), time.process_time()
    output = assemble(rows, scores, groups, draws, reference=reference)
    output.update(
        header_binding=sha(canonical(header)),
        scores_sha256=file_hash(directory / "scores.jsonl"),
        draws_sha256=sha(draw_bytes),
        groups_sha256=sha(canonical(groups)),
    )
    if reference:
        require(
            output == read_json(directory / "metrics.json"),
            "independent_reassembly_mismatch",
        )
        json_persist(
            directory / "reassembly.json",
            {
                "status": "PASS",
                "method": (
                    "expanded average-rank AUC; saved score ledger and shared "
                    "draws; no text/scorer"
                ),
                "metrics_sha256": sha(canonical(output)),
                "draws_sha256": sha(draw_bytes),
                "elapsed_seconds": time.monotonic() - started,
                "cpu_seconds": time.process_time() - cpu,
            },
        )
    else:
        json_persist(directory / "metrics.json", output)
        new_json(
            directory / "metrics_execution.json",
            {
                "elapsed_seconds": time.monotonic() - started,
                "cpu_seconds": time.process_time() - cpu,
            },
        )
    print(
        "independent reassembly PASS" if reference else "complete metrics saved",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "preflight",
            "score",
            "verify",
            "metrics",
            "verify-results",
            "recover-tail",
        ),
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    directory = repo / "eval/results/r1g"
    if args.operation in ("preflight", "score"):
        run(repo, directory, args.operation == "preflight")
    elif args.operation == "verify":
        verify_saved(repo, directory)
        print("complete ledger verification PASS")
    elif args.operation in ("metrics", "verify-results"):
        metrics(repo, directory, args.operation == "verify-results")
    else:
        accepted = accepted_state(repo)
        header = read_json(directory / "header.json")
        validate_header(repo, accepted, header)
        check_hashes(repo, header["evaluation_sources_sha256"])
        rows = {r["id"]: r for r in accepted_state(repo)["rows"]}
        with writer_lock(directory):
            recover_tail(
                directory / "journal.jsonl",
                list(rows),
                sha(canonical(header)),
                lambda result, rid: validate_result(result, rows[rid], header),
            )


if __name__ == "__main__":
    main()
