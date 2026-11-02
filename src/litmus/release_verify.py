"""Supported, repeatable read-only verification of the completed R1 evaluation.

Historical G scoring/recovery commands remain immutable provenance, not release
operations. This module never opens test blobs/models or offers scoring/resume.
"""

import argparse
import json
from pathlib import Path

from litmus.calibration_run import git, read_json
from litmus.data_prep.acquisition import file_hash
from litmus.data_prep.keys import canonical
from litmus.evaluation.gate import accepted_state
from litmus.evaluation.journal import parse
from litmus.evaluation.metrics import assemble
from litmus.evaluation.run import (
    IDENTITY,
    validate_header,
    validate_result,
    verify_saved,
)
from litmus.scorer.calibration import require, sha, strict_json

RESULTS_COMMIT = "99cf803c319b1b017f92b252d1b773f4be7b8b1e"
RECEIPT = "eval/results/r1g_verification.json"


def strict_journal(data, rows, header, validate):
    require(not data or data.endswith(b"\n"), "truncated_journal")
    by_id = {r["id"]: r for r in rows}
    require(len(by_id) == len(rows), "duplicate_input_id")
    binding = sha(canonical(header))
    for line in data.splitlines():
        e = strict_json(line)
        require(
            set(e) == {"event", "id", "attempt", "time", "binding", "data"},
            "journal_fields",
        )
        require(e["id"] in by_id and e["binding"] == binding, "journal_identity")
        require(
            type(e["attempt"]) is int
            and e["attempt"] > 0
            and isinstance(e["time"], str),
            "journal_attempt_or_time",
        )
        require(isinstance(e["data"], dict), "journal_payload")
        row = by_id[e["id"]]
        if e["event"] == "intent":
            require(e["data"] == {k: row[k] for k in IDENTITY}, "intent_identity")
        elif e["event"] == "access":
            expected = {
                "outcome": "read",
                "raw_text_sha256": row["raw_text_sha256"],
                "bytes": row["utf8_bytes"],
            }
            require(
                e["data"] == expected and type(e["data"]["bytes"]) is int,
                "access_identity",
            )
        else:
            require(e["event"] == "completion", "unsupported_or_aborted_event")
    # Check the entire sequence and completeness before any downstream callback.
    done, pending, _ = parse(data, list(by_id), binding, lambda *args: None)
    require(len(done) == len(rows) and pending is None, "incomplete_evaluation")
    return parse(data, list(by_id), binding, validate)[0]


def verify(repo, *, metrics=False):
    repo = Path(repo).resolve()
    receipt_path = repo / RECEIPT
    require(
        receipt_path.read_bytes() == git(repo, "show", RESULTS_COMMIT + ":" + RECEIPT),
        "accepted_g_receipt_changed",
    )
    receipt = read_json(receipt_path)
    for path, digest in receipt["files_sha256"].items():
        require(file_hash(repo / path) == digest, "g_artifact_changed:" + path)
    accepted = accepted_state(repo)
    directory = repo / "eval/results/r1g"
    header = read_json(directory / "header.json")
    validate_header(repo, accepted, header)
    rows = accepted["rows"]
    by_id = {r["id"]: r for r in rows}
    strict_journal(
        (directory / "journal.jsonl").read_bytes(),
        rows,
        header,
        lambda value, rid: validate_result(value, by_id[rid], header),
    )
    # Only now invoke historical full verification; it never reads test text.
    verify_saved(repo, directory)
    result = {
        "schema": "r1-release-verification/v1",
        "status": "PASS",
        "rows": 3361,
        "groups": 675,
        "strict_journal": "PASS",
        "frozen_e_f_and_original_g_identities": "PASS",
        "scientific_artifacts": len(receipt["files_sha256"]),
        "metrics_reassembly": "not requested",
        "historical_recovery": "unmet requirement; legacy execution retired",
        "historical_transfer_compliance_proven": False,
    }
    if metrics:
        scores = [
            strict_json(line)
            for line in (directory / "scores.jsonl").read_bytes().splitlines()
        ]
        groups = read_json(directory / "bootstrap_groups.json")["groups"]
        draws = [
            json.loads(line)
            for line in (directory / "bootstrap_draws.jsonl").read_bytes().splitlines()
        ]
        actual = assemble(rows, scores, groups, draws, reference=True)
        actual.update(
            header_binding=sha(canonical(header)),
            scores_sha256=file_hash(directory / "scores.jsonl"),
            draws_sha256=file_hash(directory / "bootstrap_draws.jsonl"),
            groups_sha256=sha(canonical(groups)),
        )
        require(actual == read_json(directory / "metrics.json"), "reassembly_mismatch")
        result.update(metrics_reassembly="PASS", metrics_sha256=sha(canonical(actual)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="reassemble saved metrics/draws without scoring",
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.repo, metrics=args.metrics), sort_keys=True))


if __name__ == "__main__":
    main()
