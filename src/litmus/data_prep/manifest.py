"""Deterministic scientific ledgers, no raw text or mutable timing identity."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from litmus.data_prep.acquisition import PrepError, file_hash, write_json
from litmus.data_prep.cleanup import within_group_equalities
from litmus.data_prep.keys import ROW, SELECT, SPLIT, canonical, key, split_source
from litmus.data_prep.schema import ATTACKS, DOMAINS, MODELS

LEDGERS = (
    "candidates.jsonl",
    "retained.jsonl",
    "exclusions.jsonl",
    "collisions.jsonl",
    "noops.jsonl",
    "counts.json",
)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        for row in rows:
            stream.write(canonical(row) + b"\n")


def load_jsonl(path):
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def count_slices(rows):
    dimensions = (
        "split",
        "domain",
        "model",
        "attack",
        "role",
        "decoding",
        "repetition_penalty",
    )
    declared = {
        "split": ("dev", "test"),
        "domain": DOMAINS,
        "model": MODELS | {"human"},
        "attack": ATTACKS | {"none"},
        "role": ("human", "machine", "attack"),
        "decoding": ("", "greedy", "sampling"),
        "repetition_penalty": ("", "yes", "no"),
    }
    result = {}
    for name in dimensions:
        values = Counter({value: 0 for value in declared[name]})
        values.update(r[name] for r in rows)
        result[name] = dict(sorted(values.items()))
    return result


def joint_slices(rows):
    counts = Counter((r["split"], r["domain"], r["model"], r["attack"]) for r in rows)
    return [
        {
            "split": split,
            "domain": domain,
            "model": model,
            "attack": attack,
            "rows": counts[split, domain, model, attack],
        }
        for split in ("dev", "test")
        for domain in sorted(DOMAINS)
        for model in sorted(MODELS | {"human"})
        for attack in sorted(ATTACKS | {"none"})
    ]


def assert_invariants(rows, candidates, seed):
    if len({r["id"] for r in rows}) != len(rows):
        raise PrepError("duplicate_retained_id")
    chosen = {g["source_id"]: g for g in candidates}
    if len(chosen) != len(candidates):
        raise PrepError("candidate_source_reused")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["source_id"]].append(row)
        if row["split"] != split_source(seed, row["source_id"]):
            raise PrepError("group_split_mismatch")
    for sid, members in grouped.items():
        group = chosen[sid]
        allowed = {
            group["human_id"]: ("human", "none"),
            group["machine_id"]: ("machine", "none"),
        }
        allowed.update(
            {rid: ("attack", attack) for attack, rid in group["attack_ids"].items()}
        )
        if (
            sum(r["role"] == "human" for r in members) != 1
            or sum(r["role"] == "machine" for r in members) != 1
        ):
            raise PrepError("clean_pair_invariant_failed")
        ids = {r["id"] for r in members}
        if not {group["human_id"], group["machine_id"]} <= ids:
            raise PrepError("selected_clean_pair_changed")
        for row in members:
            if allowed.get(row["id"]) != (row["role"], row["attack"]):
                raise PrepError("retained_role_or_identity_changed")
            if row["model"] != ("human" if row["role"] == "human" else group["model"]):
                raise PrepError("retained_model_changed")
            if row["domain"] != group["domain"]:
                raise PrepError("group_domain_changed")
            if row["role"] == "attack":
                if (
                    row["adv_source_id"] != group["machine_id"]
                    or group["attack_ids"].get(row["attack"]) != row["id"]
                ):
                    raise PrepError("attack_parent_invariant_failed")
    for channel in ("raw_text_sha256", "scored_window_sha256"):
        identities = {}
        for row in rows:
            previous = identities.setdefault(row[channel], row["source_id"])
            if previous != row["source_id"]:
                raise PrepError("cross_group_collision_remains")
    for group in candidates:
        if group["select_key"] != key(SELECT, seed, group["source_id"]).hex():
            raise PrepError("candidate_select_key_changed")
        for role in ("human", "machine"):
            if group[role + "_row_key"] != key(ROW, seed, group[role + "_id"]).hex():
                raise PrepError("candidate_row_key_changed")
        if group["attack_row_keys"] != {
            a: key(ROW, seed, rid).hex() for a, rid in group["attack_ids"].items()
        }:
            raise PrepError("attack_row_key_changed")
        if group["split_key"] != key(SPLIT, seed, group["source_id"]).hex():
            raise PrepError("candidate_split_key_changed")
        if group["split"] != split_source(seed, group["source_id"]):
            raise PrepError("candidate_split_changed")


def write_manifest(output, payload):
    payload["ledger_sha256"] = {name: file_hash(output / name) for name in LEDGERS}
    for split in ("dev", "test"):
        members = [
            r for r in load_jsonl(output / "retained.jsonl") if r["split"] == split
        ]
        payload.setdefault("split_sha256", {})[split] = hashlib.sha256(
            b"".join(canonical(r) + b"\n" for r in members)
        ).hexdigest()
    envelope = {
        "payload": payload,
        "manifest_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
    }
    write_json(output / "manifest.json", envelope)
    return envelope


def validate_manifest(output):
    output = Path(output)
    envelope = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    payload = envelope["payload"]
    if hashlib.sha256(canonical(payload)).hexdigest() != envelope["manifest_sha256"]:
        raise PrepError("manifest_identity_mismatch")
    if set(payload["ledger_sha256"]) != set(LEDGERS):
        raise PrepError("ledger_list_mismatch")
    for name, digest in payload["ledger_sha256"].items():
        if file_hash(output / name) != digest:
            raise PrepError("ledger_identity_mismatch:" + name)
    candidates = load_jsonl(output / "candidates.jsonl")
    retained = load_jsonl(output / "retained.jsonl")
    assert_invariants(retained, candidates, payload["seed"])
    counts = json.loads((output / "counts.json").read_text(encoding="utf-8"))
    if counts["retained_slices"] != count_slices(retained):
        raise PrepError("retained_count_mismatch")
    if counts["retained_joint_slices"] != joint_slices(retained):
        raise PrepError("retained_joint_count_mismatch")
    if counts["within_group_equalities"] != within_group_equalities(retained):
        raise PrepError("within_group_audit_mismatch")
    dev_humans = sum(r["role"] == "human" and r["split"] == "dev" for r in retained)
    if counts["eligible_development_humans"] != dev_humans or (
        payload["eligible_development_humans"] != dev_humans
    ):
        raise PrepError("development_human_count_mismatch")
    if counts["retained_rows"] != len(retained) or counts["retained_groups"] != len(
        {r["source_id"] for r in retained}
    ):
        raise PrepError("retained_total_mismatch")
    for split, digest in payload["split_sha256"].items():
        actual = hashlib.sha256(
            b"".join(canonical(r) + b"\n" for r in retained if r["split"] == split)
        ).hexdigest()
        if actual != digest:
            raise PrepError("split_manifest_identity_mismatch")
    return envelope, candidates, retained
