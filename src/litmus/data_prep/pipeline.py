"""Approved R1-E metadata selection -> tokenizer eligibility -> frozen ledgers."""

import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import asdict

from litmus.data_prep.acquisition import (
    REVISION,
    SHA256,
    SIZE,
    Budget,
    PrepError,
    directory_bytes,
    file_hash,
    write_json,
)
from litmus.data_prep.cleanup import cleanup, within_group_equalities
from litmus.data_prep.keys import ROW, SELECT, SPLIT, canonical
from litmus.data_prep.manifest import (
    assert_invariants,
    count_slices,
    joint_slices,
    write_jsonl,
    write_manifest,
)
from litmus.data_prep.resources import memory_usage
from litmus.data_prep.schema import (
    ATTACKS,
    index_metadata,
    indexed_rows,
    iter_csv,
    metadata,
)
from litmus.data_prep.selection import SEED, TARGET, attach_attacks, select_groups
from litmus.data_prep.text import assess


def source_identity(repo):
    paths = sorted((repo / "src/litmus/data_prep").glob("*.py"))
    paths += [repo / "src/litmus/config.py", repo / "src/litmus/scorer/tokenize.py"]
    paths += [
        repo / "scripts" / name
        for name in ("acquire_raid.py", "prepare_raid.py", "verify_raid_manifest.py")
    ]
    return {p.relative_to(repo).as_posix(): file_hash(p) for p in paths}


def metadata_digest(db):
    digest = hashlib.sha256()
    for values in db.execute("SELECT * FROM rows ORDER BY id"):
        digest.update(canonical(list(values)) + b"\n")
    return digest.hexdigest()


def candidate_roles(groups):
    roles = {}
    for group in groups:
        for identifier, role, attack in [
            (group["human_id"], "human", "none"),
            (group["machine_id"], "machine", "none"),
            *((rid, "attack", a) for a, rid in group["attack_ids"].items()),
        ]:
            if identifier in roles:
                raise PrepError("candidate_row_reused")
            roles[identifier] = (group, role, attack)
    return roles


def prepare(
    repo,
    run_id,
    tokenizer,
    tokenizer_identity,
    *,
    raw=None,
    target=TARGET,
    seed=SEED,
    expected_sha=SHA256,
    expected_size=SIZE,
):
    start, cpu_start = time.monotonic(), time.process_time()
    raw = raw or repo / "data/raid" / REVISION / "train.csv"
    if raw.stat().st_size != expected_size or file_hash(raw) != expected_sha:
        raise PrepError("raw_identity_preparation_preflight_failed")
    local = repo / "data/raid/prepared" / run_id
    output = repo / "eval/manifests/r1e" / run_id
    if local.exists() or output.exists():
        raise PrepError("run_output_already_exists; preserve it and use a new run id")
    local.mkdir(parents=True)
    output.mkdir(parents=True)
    budget = Budget(
        repo / "data/raid",
        extra_roots=(repo / "eval/manifests/r1e",),
        reserve=64 * 1024 * 1024,
    )
    db, scanned = index_metadata(raw, local / "metadata.sqlite", budget)
    try:
        groups, selection = select_groups(
            indexed_rows(db, clean=True), seed=seed, target=target
        )
        groups, metadata_exclusions, attachment = attach_attacks(
            indexed_rows(db), groups, seed=seed
        )
        meta_hash = metadata_digest(db)
    finally:
        db.close()
    roles = candidate_roles(groups)
    write_jsonl(
        output / "candidates.jsonl", groups
    )  # frozen before content eligibility
    print(f"Frozen {len(groups)} groups / {len(roles)} candidate rows", flush=True)
    eligible, excluded, seen = [], list(metadata_exclusions), set()
    (local / "texts").mkdir()
    scanned_content = 0
    for raw_row in iter_csv(raw):
        scanned_content += 1
        rid = raw_row["id"]
        if rid not in roles:
            continue
        if rid in seen:
            raise PrepError("duplicate_selected_row_identity")
        seen.add(rid)
        group, role, attack = roles[rid]
        item = metadata(raw_row)
        if item.source_id != group["source_id"] or item.domain != group["domain"]:
            raise PrepError("selected_row_metadata_changed")
        observed, reasons = assess(raw_row["generation"], tokenizer)
        if reasons:
            excluded.append(
                {
                    "id": rid,
                    "source_id": item.source_id,
                    "stage": "eligibility",
                    "reasons": reasons,
                }
            )
        else:
            if len(eligible) % 50 == 0:
                budget.check_storage(50 * 800000)
            blob = "texts/" + observed["raw_text_sha256"] + ".txt"
            destination = local / blob
            if not destination.exists():
                destination.write_bytes(raw_row["generation"].encode("utf-8"))
            eligible.append(
                {
                    **asdict(item),
                    **observed,
                    "role": role,
                    "attack": attack,
                    "split": group["split"],
                    "text_blob": blob,
                }
            )
        if len(seen) % 1000 == 0:
            print(f"Inspected {len(seen):,} selected texts", flush=True)
    if scanned_content != scanned["rows_scanned"] or seen != set(roles):
        raise PrepError("content_pass_row_count_or_identity_mismatch")
    retained, exclusions, collisions, noops = cleanup(eligible, groups, excluded)
    assert_invariants(retained, groups, seed)
    for name, values in (
        ("retained.jsonl", retained),
        ("exclusions.jsonl", exclusions),
        ("collisions.jsonl", collisions),
        ("noops.jsonl", noops),
    ):
        write_jsonl(output / name, values)
    kept_sources = {r["source_id"] for r in retained}
    dev_humans = sum(r["role"] == "human" and r["split"] == "dev" for r in retained)
    candidate_rows = []
    for rid, (group, role, attack) in roles.items():
        settings = (
            group["human_metadata"] if role == "human" else group["machine_metadata"]
        )
        candidate_rows.append(
            {
                "id": rid,
                "source_id": group["source_id"],
                "domain": group["domain"],
                "split": group["split"],
                "model": "human" if role == "human" else group["model"],
                "role": role,
                "attack": attack,
                "decoding": settings["decoding"],
                "repetition_penalty": settings["repetition_penalty"],
            }
        )
    exclusion_counts = Counter(r["primary_reason"] for r in exclusions)
    candidate_excluded = {r["id"] for r in exclusions if r["id"] in roles}
    if len(retained) + len(candidate_excluded) != len(roles):
        raise PrepError("candidate_row_reconciliation_failed")
    counts = {
        "scan": scanned,
        "selection": selection,
        "attack_attachment": attachment,
        "candidate_groups": len(groups),
        "candidate_rows": len(roles),
        "candidate_slices": count_slices(candidate_rows),
        "candidate_joint_slices": joint_slices(candidate_rows),
        "eligible_before_dedup": len(eligible),
        "exclusions": len(exclusions),
        "candidate_excluded": len(candidate_excluded),
        "exclusions_by_primary_reason": dict(sorted(exclusion_counts.items())),
        "retained_groups": len(kept_sources),
        "retained_rows": len(retained),
        "post_selection_group_attrition": len(groups) - len(kept_sources),
        "retained_slices": count_slices(retained),
        "retained_joint_slices": joint_slices(retained),
        "collisions": len(collisions),
        "raw_noops": sum(n["raw_noop"] for n in noops),
        "window_noops": sum(n["window_noop"] for n in noops),
        "within_group_equalities": within_group_equalities(retained),
        "eligible_development_humans": dev_humans,
        "future_5pct_calibration_count_eligible": dev_humans >= 200,
        "calibration_created": False,
        "scoring_performed": False,
        "missing_candidate_attacks": {
            a: sum(a not in g["attack_ids"] for g in groups) for a in sorted(ATTACKS)
        },
        "retained_groups_by_split": dict(
            sorted(
                Counter(r["split"] for r in retained if r["role"] == "human").items()
            )
        ),
        "retained_cells": [
            {
                "domain": c["domain"],
                "model": c["model"],
                "groups": sum(
                    g["source_id"] in kept_sources
                    and g["domain"] == c["domain"]
                    and g["model"] == c["model"]
                    for g in groups
                ),
            }
            for c in selection["cells"]
        ],
    }
    write_json(output / "counts.json", counts)
    envelope = write_manifest(
        output,
        {
            "schema_version": 1,
            "algorithm_version": "r1e-1",
            "seed": seed,
            "N_target": target,
            "key_tags": [SELECT, SPLIT, ROW],
            "key_encoding": (
                "UTF8 compact JSON [tag,integer_seed,string_id]; ensure_ascii=false"
            ),
            "raw_text_hash_encoding": "exact generation UTF-8 bytes",
            "window_hash_encoding": "UTF8 compact JSON retained integer token-ID array",
            "dataset": {
                "repository": "liamdugan/raid",
                "revision": REVISION,
                "file": "train.csv",
                "bytes": expected_size,
                "sha256": expected_sha,
            },
            "tokenizer": tokenizer_identity,
            "source_sha256": source_identity(repo),
            "source_hash_policy": (
                "exact bytes; declared source files use LF via .gitattributes"
            ),
            "metadata_index_sha256": meta_hash,
            "eligible_development_humans": dev_humans,
            "scoring_performed": False,
            "invariants": "PASS",
        },
    )
    telemetry = {
        "run_id": run_id,
        "elapsed_seconds": time.monotonic() - start,
        "cpu_seconds": time.process_time() - cpu_start,
        "local_artifact_bytes": directory_bytes(local),
        "task_artifacts_with_reserve": budget.check_storage(),
        "manifest_sha256": envelope["manifest_sha256"],
        "python": sys.version,
        "memory": memory_usage(),
        "counts": counts,
    }
    write_json(repo / "eval/results" / f"r1e_{run_id}_run.json", telemetry)
    print(
        json.dumps(
            {
                k: counts[k]
                for k in (
                    "candidate_groups",
                    "retained_groups",
                    "retained_rows",
                    "eligible_development_humans",
                )
            }
        ),
        flush=True,
    )
    return envelope
