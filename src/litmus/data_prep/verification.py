"""Offline verification against raw CSV, metadata selection and local text blobs."""

import json
import sqlite3
import time
from dataclasses import asdict

from litmus.data_prep import pipeline as prep
from litmus.data_prep.acquisition import PrepError, file_hash
from litmus.data_prep.cleanup import cleanup
from litmus.data_prep.manifest import LEDGERS, load_jsonl, validate_manifest
from litmus.data_prep.schema import indexed_rows, iter_csv, metadata
from litmus.data_prep.selection import attach_attacks, select_groups
from litmus.data_prep.text import assess

# Only the acquisition correction and its verifier/CLI seam may differ from
# the historical preparation. Selection, eligibility and cleanup must match.
RECONCILABLE_SOURCE_CHANGES = frozenset(
    (
        "src/litmus/data_prep/acquisition.py",
        "src/litmus/data_prep/verification.py",
        "scripts/verify_raid_manifest.py",
    )
)


def verify_source_version(repo, envelope, reconciliation=None):
    historical = envelope["payload"]["source_sha256"]
    current = prep.source_identity(repo)
    if reconciliation is None:
        if historical != current:
            raise PrepError("preparation_source_identity_changed")
        return {"mode": "exact_preparation_source_match"}
    record = json.loads(reconciliation.read_text(encoding="utf-8"))
    changed = {
        p
        for p in historical.keys() | current.keys()
        if historical.get(p) != current.get(p)
    }
    if (
        record.get("schema_version") != 1
        or record.get("historical_manifest_sha256") != envelope["manifest_sha256"]
        or record.get("historical_source_sha256") != historical
        or record.get("verification_source_sha256") != current
        or set(historical) != set(current)
        or record.get("changed_sources") != sorted(changed)
        or not changed <= RECONCILABLE_SOURCE_CHANGES
    ):
        raise PrepError("source_reconciliation_mismatch")
    return {
        "mode": "explicit_historical_source_reconciliation",
        "record_sha256": file_hash(reconciliation),
        "historical_manifest_sha256": envelope["manifest_sha256"],
        "changed_sources": sorted(changed),
        "historical_generation_source_identity_unchanged": True,
    }


def verify(repo, run_id, tokenizer, identity, *, raw=None, source_reconciliation=None):
    started = time.monotonic()
    output = repo / "eval/manifests/r1e" / run_id
    local = repo / "data/raid/prepared" / run_id
    envelope, candidates, retained = validate_manifest(output)
    payload = envelope["payload"]
    if payload["tokenizer"] != identity:
        raise PrepError("verification_tokenizer_identity_mismatch")
    source_version = verify_source_version(repo, envelope, source_reconciliation)
    raw = raw or repo / "data/raid" / payload["dataset"]["revision"] / "train.csv"
    if raw.stat().st_size != payload["dataset"]["bytes"] or (
        file_hash(raw) != payload["dataset"]["sha256"]
    ):
        raise PrepError("verification_raw_identity_mismatch")
    db = sqlite3.connect(
        f"file:{(local / 'metadata.sqlite').as_posix()}?mode=ro", uri=True
    )
    try:
        if prep.metadata_digest(db) != payload["metadata_index_sha256"]:
            raise PrepError("metadata_index_changed")
        groups, selection = select_groups(
            indexed_rows(db, clean=True),
            seed=payload["seed"],
            target=payload["N_target"],
        )
        groups, metadata_exclusions, attachment = attach_attacks(
            indexed_rows(db), groups, seed=payload["seed"]
        )
    finally:
        db.close()
    if groups != candidates:
        raise PrepError("metadata_selection_reproduction_failed")
    counts = json.loads((output / "counts.json").read_text(encoding="utf-8"))
    if selection != counts["selection"] or attachment != counts["attack_attachment"]:
        raise PrepError("metadata_count_reproduction_failed")
    roles = prep.candidate_roles(candidates)
    kept_by_id = {r["id"]: r for r in retained}
    eligible, excluded, seen, scanned = [], list(metadata_exclusions), set(), 0
    for raw_row in iter_csv(raw):
        scanned += 1
        rid = raw_row["id"]
        if rid not in roles:
            continue
        if rid in seen:
            raise PrepError("duplicate_selected_identity_on_verification")
        seen.add(rid)
        group, role, attack = roles[rid]
        item = metadata(raw_row)
        observed, errors = assess(raw_row["generation"], tokenizer)
        if errors:
            excluded.append(
                {
                    "id": rid,
                    "source_id": item.source_id,
                    "stage": "eligibility",
                    "reasons": errors,
                }
            )
        else:
            record = {
                **asdict(item),
                **observed,
                "role": role,
                "attack": attack,
                "split": group["split"],
                "text_blob": "texts/" + observed["raw_text_sha256"] + ".txt",
            }
            eligible.append(record)
            if rid in kept_by_id:
                if record != kept_by_id[rid]:
                    raise PrepError("retained_row_does_not_match_raw_csv")
                blob = (local / record["text_blob"]).resolve()
                if not blob.is_relative_to(local.resolve()) or (
                    blob.read_bytes() != raw_row["generation"].encode("utf-8")
                ):
                    raise PrepError("text_blob_identity_mismatch")
        if len(seen) % 1000 == 0:
            print(f"Verified {len(seen):,} selected raw texts", flush=True)
    if seen != set(roles) or scanned != counts["scan"]["rows_scanned"]:
        raise PrepError("verification_input_count_mismatch")
    actual = cleanup(eligible, groups, excluded)
    for name, values in zip(
        ("retained.jsonl", "exclusions.jsonl", "collisions.jsonl", "noops.jsonl"),
        actual,
        strict=True,
    ):
        if values != load_jsonl(output / name):
            raise PrepError("cleanup_reproduction_failed:" + name)
    return {
        "status": "PASS",
        "run_id": run_id,
        "raw_rows_scanned": scanned,
        "selected_texts_recomputed": len(seen),
        "retained_text_blobs_verified": len(retained),
        "manifest_sha256": envelope["manifest_sha256"],
        "source_version": source_version,
        "elapsed_seconds": time.monotonic() - started,
    }


def compare_runs(repo, first="primary", second="repeat"):
    root = repo / "eval/manifests/r1e"
    for name in (*LEDGERS, "manifest.json"):
        if (root / first / name).read_bytes() != (root / second / name).read_bytes():
            raise PrepError("repeat_run_mismatch:" + name)
    return {
        "status": "PASS",
        "files_compared": [*LEDGERS, "manifest.json"],
        "scientific_identity": json.loads(
            (root / first / "manifest.json").read_text(encoding="utf-8")
        )["manifest_sha256"],
    }
