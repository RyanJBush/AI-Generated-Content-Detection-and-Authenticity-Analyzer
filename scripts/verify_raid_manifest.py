"""Verify approved prepared RAID records without network, scores, weights or CUDA."""

import argparse
from pathlib import Path

from litmus.data_prep.acquisition import REVISION, SHA256, SIZE, PrepError, write_json
from litmus.data_prep.guards import preparation_guards
from litmus.data_prep.manifest import validate_manifest
from litmus.data_prep.selection import SEED, TARGET
from litmus.data_prep.text import load_local_tokenizer
from litmus.data_prep.verification import compare_runs, verify

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", choices=("primary", "repeat"), default="primary")
    parser.add_argument("--compare-repeat", action="store_true")
    parser.add_argument("--source-reconciliation", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.source_reconciliation and args.output is None:
        parser.error("--source-reconciliation requires a new --output receipt")
    output = (
        args.output or repo / "eval/results" / f"r1e_{args.run_id}_verification.json"
    )
    if output.exists():
        raise PrepError("verification_receipt_already_exists; use a new --output")
    envelope, _, _ = validate_manifest(repo / "eval/manifests/r1e" / args.run_id)
    payload = envelope["payload"]
    if (
        payload["seed"] != SEED
        or payload["N_target"] != TARGET
        or payload["dataset"]
        != {
            "repository": "liamdugan/raid",
            "revision": REVISION,
            "file": "train.csv",
            "bytes": SIZE,
            "sha256": SHA256,
        }
    ):
        raise PrepError("manifest_not_the_approved_study")
    with preparation_guards() as attempts:
        tokenizer, identity = load_local_tokenizer(repo)
        result = verify(
            repo,
            args.run_id,
            tokenizer,
            identity,
            source_reconciliation=args.source_reconciliation,
        )
        if args.compare_repeat:
            result["repeat_run"] = compare_runs(repo)
    result["guards"] = attempts
    write_json(output, result)
    print(result)
