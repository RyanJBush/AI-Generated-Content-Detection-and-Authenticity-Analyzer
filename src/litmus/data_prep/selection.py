"""Metadata-only quotas; source uniqueness and independent tagged keys."""

import hashlib
from collections import Counter, defaultdict
from dataclasses import asdict

from litmus.data_prep.acquisition import PrepError
from litmus.data_prep.keys import ROW, SELECT, SPLIT, canonical, key, split_source
from litmus.data_prep.schema import ATTACKS, DOMAINS, MODELS

SEED = 20261030
TARGET = 1000


def select_groups(rows, *, seed=SEED, target=TARGET):
    ignored = Counter()
    sources = defaultdict(lambda: {"domains": set(), "humans": [], "machines": []})
    for item in rows:
        if item.attack != "none":
            continue
        source = sources[item.source_id]
        source["domains"].add(item.domain)
        if item.model == "human":
            source["humans"].append(item)
        elif (
            item.model in MODELS
            and item.decoding in ("greedy", "sampling")
            and (item.repetition_penalty in ("yes", "no"))
        ):
            source["machines"].append(item)
        else:
            ignored[
                "unknown_model"
                if item.model not in MODELS
                else "invalid_machine_settings"
            ] += 1
    eligible, rejected, frame = {}, Counter(), hashlib.sha256()
    for source_id in sorted(sources):
        source = sources[source_id]
        if len(source["domains"]) != 1:
            rejected["ambiguous_domain"] += 1
        elif next(iter(source["domains"])) not in DOMAINS:
            rejected["domain_excluded"] += 1
        elif len(source["humans"]) != 1:
            rejected["ambiguous_or_missing_human"] += 1
        elif not source["machines"]:
            rejected["no_eligible_clean_machine"] += 1
        else:
            domain = next(iter(source["domains"]))
            eligible[source_id] = source
            values = sorted(source["humans"] + source["machines"], key=lambda r: r.id)
            frame.update(
                canonical([source_id, domain, [asdict(r) for r in values]]) + b"\n"
            )
    cells = sorted(
        {
            (next(iter(s["domains"])), r.model)
            for s in eligible.values()
            for r in s["machines"]
        }
    )
    if not cells:
        raise PrepError("no_selectable_population")
    quotas = {
        cell: target // len(cells) + (i < target % len(cells))
        for i, cell in enumerate(cells)
    }
    queues = {}
    for domain, model in cells:
        ids = [
            sid
            for sid, s in eligible.items()
            if domain in s["domains"] and any(r.model == model for r in s["machines"])
        ]
        queues[domain, model] = iter(
            sorted(ids, key=lambda s: (key(SELECT, seed, s), s))
        )
    assigned, used, exhausted = Counter(), set(), set()
    selected = []
    while True:
        progressed = False
        for cell in cells:
            if assigned[cell] >= quotas[cell] or cell in exhausted:
                continue
            sid = next((sid for sid in queues[cell] if sid not in used), None)
            if sid is None:
                exhausted.add(cell)
                continue
            used.add(sid)
            source = eligible[sid]
            machine = min(
                (r for r in source["machines"] if r.model == cell[1]),
                key=lambda r: (key(ROW, seed, r.id), r.id),
            )
            human = source["humans"][0]
            selected.append(
                {
                    "source_id": sid,
                    "domain": cell[0],
                    "model": cell[1],
                    "human_id": human.id,
                    "human_metadata": asdict(human),
                    "machine_id": machine.id,
                    "machine_metadata": asdict(machine),
                    "select_key": key(SELECT, seed, sid).hex(),
                    "split_key": key(SPLIT, seed, sid).hex(),
                    "machine_row_key": key(ROW, seed, machine.id).hex(),
                    "human_row_key": key(ROW, seed, human.id).hex(),
                    "split": split_source(seed, sid),
                    "attack_ids": {},
                }
            )
            assigned[cell] += 1
            progressed = True
        if not progressed:
            break
    return sorted(selected, key=lambda g: g["source_id"]), {
        "metadata_sources": len(sources),
        "eligible_sources": len(eligible),
        "source_rejections": dict(rejected),
        "clean_rows_ignored": dict(ignored),
        "eligible_frame_sha256": frame.hexdigest(),
        "cells": [
            {
                "domain": d,
                "model": m,
                "quota": quotas[d, m],
                "assigned": assigned[d, m],
                "shortfall": quotas[d, m] - assigned[d, m],
            }
            for d, m in cells
        ],
    }


def attach_attacks(rows, groups, *, seed=SEED):
    parents = {g["machine_id"]: g for g in groups}
    winners, excluded, counts = {}, [], Counter()
    for item in rows:
        if item.attack not in ATTACKS:
            counts["out_of_attack_scope"] += 1
            continue
        group = parents.get(item.adv_source_id)
        if group is None:
            counts["attacks_not_selected_parent"] += 1
            continue
        parent = group["machine_metadata"]
        if any(
            getattr(item, field) != parent[field]
            for field in (
                "source_id",
                "domain",
                "model",
                "decoding",
                "repetition_penalty",
            )
        ):
            excluded.append(
                {
                    "id": item.id,
                    "source_id": item.source_id,
                    "stage": "attack_metadata",
                    "reasons": ["parent_mismatch"],
                }
            )
            counts["mismatched_attacks"] += 1
            continue
        index = item.adv_source_id, item.attack
        previous = winners.get(index)
        if previous is None:
            winners[index] = item
        else:
            winner, loser = sorted(
                [previous, item], key=lambda r: (key(ROW, seed, r.id), r.id)
            )
            winners[index] = winner
            excluded.append(
                {
                    "id": loser.id,
                    "source_id": loser.source_id,
                    "stage": "attack_tie",
                    "reasons": ["attack_tie_not_selected"],
                }
            )
            counts["attack_ties_discarded"] += 1
    result = []
    for group in groups:
        value = dict(group)
        value["attack_ids"] = {
            attack: winners[group["machine_id"], attack].id
            for attack in sorted(ATTACKS)
            if (group["machine_id"], attack) in winners
        }
        value["attack_row_keys"] = {
            a: key(ROW, seed, rid).hex() for a, rid in value["attack_ids"].items()
        }
        result.append(value)
    return result, sorted(excluded, key=lambda r: r["id"]), dict(counts)
