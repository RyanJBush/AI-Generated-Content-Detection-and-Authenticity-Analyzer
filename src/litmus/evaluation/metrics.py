"""Predeclared pure grouped statistics; never reads text or calls a model."""

import math
import random
from collections import Counter, defaultdict

from litmus.data_prep.keys import canonical
from litmus.scorer.calibration import require, sha

POLICY = {
    "schema": "r1g-policy-v1",
    "seed": 20261030,
    "tag": "litmus/r1/bootstrap/v1",
    "replicates": 1000,
    "orientation": "r=-raw_score",
    "comparison": ">",
    "threshold_c": -0.9272342324256897,
    "draws": (
        "sorted source IDs; Random(big-endian SHA256(compact JSON [tag,seed])); "
        "G randrange(G) per replicate; shared"
    ),
    "interval": "nearest-rank ceil(V/40),ceil(39V/40); suppress if undefined>50",
    "clean_minimum": {"groups": 30, "per_class": 50},
    "paired_minimum": {"groups": 30, "pairs": 50},
    "failures": (
        "only production numerical_error terminal null; all systemic/identity/"
        "profile/integrity errors abort; no retries of terminals"
    ),
    "clean_slices": [
        "overall",
        "domain",
        "model",
        "decoding",
        "repetition_penalty",
        "domain/model",
    ],
    "paired_slices": ["overall", "domain", "model"],
    "attacks": ["homoglyph", "paraphrase", "zero_width_space"],
    "missing": "metric-specific valid masks; failures remain in group universe",
}


def auc(samples, weights):
    blocks = defaultdict(lambda: [0, 0])
    for score, positive, group in samples:
        blocks[score][int(positive)] += weights.get(group, 0)
    lower = numerator = positives = 0
    negatives = sum(block[0] for block in blocks.values())
    for score in sorted(blocks):
        n, p = blocks[score]
        numerator += p * (lower + 0.5 * n)
        lower += n
        positives += p
    return numerator / (positives * negatives) if positives and negatives else None


def reference_auc(samples, weights):
    """Independent expanded average-rank implementation (not weighted blocks)."""
    expanded = sorted((r, y) for r, y, g in samples for _ in range(weights.get(g, 0)))
    p = sum(y for _, y in expanded)
    n = len(expanded) - p
    if not p or not n:
        return None
    ranks = 0.0
    start = 0
    while start < len(expanded):
        end = start + 1
        while end < len(expanded) and expanded[end][0] == expanded[start][0]:
            end += 1
        ranks += sum(y for _, y in expanded[start:end]) * (start + 1 + end) / 2
        start = end
    return (ranks - p * (p + 1) / 2) / (p * n)


def rate(samples, weights):
    denominator = sum(weights.get(g, 0) for _, g in samples)
    return (
        sum(int(f) * weights.get(g, 0) for f, g in samples) / denominator
        if denominator
        else None
    )


def reference_rate(samples, weights):
    expanded = [int(flag) for flag, g in samples for _ in range(weights.get(g, 0))]
    return sum(expanded) / len(expanded) if expanded else None


def reference_paired(samples, weights):
    expanded = [(a, b) for a, b, g in samples for _ in range(weights.get(g, 0))]
    n = len(expanded)
    return {
        "clean_rate": sum(a for a, _ in expanded) / n if n else None,
        "attack_rate": sum(b for _, b in expanded) / n if n else None,
        "delta": sum(int(b) - int(a) for a, b in expanded) / n if n else None,
        "both": sum(a and b for a, b in expanded),
        "neither": sum(not a and not b for a, b in expanded),
        "clean_only": sum(a and not b for a, b in expanded),
        "attack_only": sum(not a and b for a, b in expanded),
        "pairs": n,
    }


def paired(samples, weights):
    counts = Counter()
    for clean, attack, group in samples:
        counts[(clean, attack)] += weights.get(group, 0)
    both, neither = counts[(True, True)], counts[(False, False)]
    clean_only, attack_only = counts[(True, False)], counts[(False, True)]
    total = sum(counts.values())
    return {
        "clean_rate": (both + clean_only) / total if total else None,
        "attack_rate": (both + attack_only) / total if total else None,
        "delta": (attack_only - clean_only) / total if total else None,
        "both": both,
        "neither": neither,
        "clean_only": clean_only,
        "attack_only": attack_only,
        "pairs": total,
    }


def draws_for(groups):
    require(groups == sorted(set(groups)) and bool(groups), "bootstrap_group_order")
    rng = random.Random(
        int.from_bytes(
            bytes.fromhex(sha(canonical([POLICY["tag"], POLICY["seed"]]))), "big"
        )
    )
    return [[rng.randrange(len(groups)) for _ in groups] for _ in range(1000)]


def validate_draws(groups, draws):
    require(draws == draws_for(groups), "bootstrap_identity_or_vectors")


def interval(values, sufficient):
    require(len(values) == 1000, "replicate_count")
    defined = sorted(v for v in values if v is not None)
    result = {
        "defined_replicates": len(defined),
        "undefined_replicates": 1000 - len(defined),
        "undefined_reason": "missing_class_or_denominator",
        "ci": None,
    }
    if not sufficient:
        result["status"] = "insufficient data; no interval"
    elif len(defined) < 950:
        result["status"] = "interval not reported (unstable resampling)"
    else:
        result.update(
            status="reported",
            ci=[
                defined[math.ceil(len(defined) / 40) - 1],
                defined[math.ceil(39 * len(defined) / 40) - 1],
            ],
        )
    return result


def clean_sufficient(groups, negatives, positives):
    return groups >= 30 and negatives >= 50 and positives >= 50


def pair_sufficient(groups, pairs):
    return groups >= 30 and pairs >= 50


def slices(rows):
    machines = [r for r in rows if r["role"] == "machine"]
    dimensions = {
        k: sorted({r[k] for r in machines}, key=str)
        for k in ("domain", "model", "decoding", "repetition_penalty")
    }
    clean = [("overall", {})]
    for k, values in dimensions.items():
        clean.extend((f"{k}={v}", {k: v}) for v in values)
    clean.extend(
        (f"domain={d}/model={m}", {"domain": d, "model": m})
        for d in dimensions["domain"]
        for m in dimensions["model"]
    )
    pair = [
        (name, mask)
        for name, mask in clean
        if not mask or len(mask) == 1 and next(iter(mask)) in ("domain", "model")
    ]
    return clean, pair


def assemble(rows, scores, groups, draws, reference=False):
    """One complete fixed population; shared draws and independent validity masks."""
    require(
        len(rows) == len(scores)
        and {r["id"] for r in rows} == {s["id"] for s in scores},
        "metric_population",
    )
    validate_draws(groups, draws)
    scored = {s["id"]: s for s in scores}
    machines = {r["source_id"]: r for r in rows if r["role"] == "machine"}
    require(sorted(machines) == groups, "metric_group_universe")
    weights = [{g: 1 for g in groups}]
    weights.extend({groups[i]: k for i, k in Counter(d).items()} for d in draws)
    clean_slices, pair_slices = slices(rows)
    output = {"clean": {}, "paired": {}, "policy_sha256": sha(canonical(POLICY))}
    auc_fn = reference_auc if reference else auc
    rate_fn = reference_rate if reference else rate
    pair_fn = reference_paired if reference else paired

    def belongs(row, mask):
        machine = machines[row["source_id"]]
        return all(machine[k] == v for k, v in mask.items())

    for name, mask in clean_slices:
        members = [r for r in rows if r["role"] != "attack" and belongs(r, mask)]
        valid = [r for r in members if scored[r["id"]]["status"] == "valid"]
        by_role = {
            role: [r for r in valid if r["role"] == role]
            for role in ("human", "machine")
        }
        points = [
            (scored[r["id"]]["oriented_score"], r["role"] == "machine", r["source_id"])
            for r in valid
        ]
        n_groups = len({r["source_id"] for r in valid})
        sufficient = clean_sufficient(
            n_groups, len(by_role["human"]), len(by_role["machine"])
        )
        values = {"auroc": [auc_fn(points, w) for w in weights]}
        for role, key in (("human", "fpr"), ("machine", "tpr")):
            samples = [(scored[r["id"]]["flag"], r["source_id"]) for r in by_role[role]]
            values[key] = [rate_fn(samples, w) for w in weights]
        output["clean"][name] = {
            "groups": n_groups,
            "requested": len(members),
            "valid": len(valid),
            "failed": len(members) - len(valid),
            "classes": {
                role: {
                    "requested": sum(r["role"] == role for r in members),
                    "valid": len(v),
                    "failed": sum(r["role"] == role for r in members) - len(v),
                    "flagged": sum(scored[r["id"]]["flag"] for r in v),
                    "groups": len({r["source_id"] for r in v}),
                }
                for role, v in by_role.items()
            },
            "metrics": {
                k: {
                    "point": v[0],
                    "point_status": "defined"
                    if v[0] is not None
                    else "undefined/missing_class_or_denominator",
                    **interval(v[1:], sufficient),
                }
                for k, v in values.items()
            },
        }

    for attack in POLICY["attacks"]:
        attacks = {
            r["source_id"]: r
            for r in rows
            if r["role"] == "attack" and r["attack"] == attack
        }
        for name, mask in pair_slices:
            parents = [r for r in machines.values() if belongs(r, mask)]
            available = [r for r in parents if r["source_id"] in attacks]
            samples, raw_noop, window_noop = [], 0, 0
            for parent in available:
                child = attacks[parent["source_id"]]
                require(
                    child["adv_source_id"] == parent["id"], "paired_parent_mismatch"
                )
                raw_noop += child["raw_text_sha256"] == parent["raw_text_sha256"]
                window_noop += (
                    child["scored_window_sha256"] == parent["scored_window_sha256"]
                )
                a, b = scored[parent["id"]], scored[child["id"]]
                if a["status"] == b["status"] == "valid":
                    samples.append((a["flag"], b["flag"], parent["source_id"]))
            values = [pair_fn(samples, w) for w in weights]
            sufficient = pair_sufficient(len({g for _, _, g in samples}), len(samples))
            result = {
                "requested_parents": len(parents),
                "available_attacks": len(available),
                "missing_attacks": len(parents) - len(available),
                "valid_pairs": len(samples),
                "groups": len({g for _, _, g in samples}),
                "raw_noops": raw_noop,
                "window_noops": window_noop,
                "failed_parents": sum(
                    scored[r["id"]]["status"] != "valid" for r in available
                ),
                "failed_attacks": sum(
                    scored[attacks[r["source_id"]]["id"]]["status"] != "valid"
                    for r in available
                ),
                "outcomes": {
                    k: v
                    for k, v in values[0].items()
                    if k not in ("clean_rate", "attack_rate", "delta")
                },
                "metrics": {},
            }
            for key in ("clean_rate", "attack_rate", "delta"):
                result["metrics"][key] = {
                    "point": values[0][key],
                    "point_status": "defined"
                    if values[0][key] is not None
                    else "undefined/no_pairs",
                    **interval([v[key] for v in values[1:]], sufficient),
                }
            output["paired"][attack + "/" + name] = result
    return output
