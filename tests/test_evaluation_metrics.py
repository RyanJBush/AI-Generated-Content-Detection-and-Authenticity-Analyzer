"""Constructed statistical tests only; no held-out text/score access."""

from collections import Counter

import pytest

from litmus.evaluation.metrics import auc, draws_for, interval, paired, rate


@pytest.mark.parametrize(
    "groups,n,p,expected",
    [(29, 50, 50, False), (30, 49, 50, False), (30, 50, 49, False), (30, 50, 50, True)],
)
def test_clean_size_boundary(groups, n, p, expected):
    from litmus.evaluation.metrics import clean_sufficient

    assert clean_sufficient(groups, n, p) is expected


@pytest.mark.parametrize(
    "groups,pairs,expected", [(29, 50, False), (30, 49, False), (30, 50, True)]
)
def test_pair_size_boundary(groups, pairs, expected):
    from litmus.evaluation.metrics import pair_sufficient

    assert pair_sufficient(groups, pairs) is expected


def synthetic_population():
    rows, scores = [], []
    for i in range(3):
        group = str(i)
        for role in ("human", "machine", "attack"):
            rid = f"{i}/{role}"
            rows.append(
                {
                    "id": rid,
                    "source_id": group,
                    "role": role,
                    "model": "human" if role == "human" else "generator",
                    "domain": "domain",
                    "decoding": "greedy",
                    "repetition_penalty": "no",
                    "attack": "homoglyph" if role == "attack" else "none",
                    "adv_source_id": f"{i}/machine" if role == "attack" else "",
                    "raw_text_sha256": "raw",
                    "scored_window_sha256": "window",
                }
            )
            scores.append(
                {
                    "id": rid,
                    "status": "valid",
                    "flag": role != "human",
                    "oriented_score": float(role != "human"),
                }
            )
    return rows, scores


def test_complete_reassembly_human_cell_failure_masks_pairs_noops():
    from litmus.evaluation.metrics import assemble

    rows, scores = synthetic_population()
    # A failed positive must not remove its independently valid human negative.
    scores[1].update(status="failed", flag=None, oriented_score=None)
    scores[5].update(status="failed", flag=None, oriented_score=None)
    groups = ["0", "1", "2"]
    draws = draws_for(groups)
    result = assemble(rows, scores, groups, draws)
    assert result == assemble(rows, scores, groups, draws, reference=True)
    clean = result["clean"]["overall"]
    assert clean["classes"]["human"]["valid"] == 3
    assert clean["classes"]["machine"]["valid"] == 2
    assert clean["metrics"]["fpr"]["point"] == 0
    assert clean["metrics"]["auroc"]["point"] == 1
    assert clean == result["clean"]["model=generator"]
    pair = result["paired"]["homoglyph/overall"]
    assert pair["valid_pairs"] == pair["failed_parents"] == pair["failed_attacks"] == 1
    assert pair["raw_noops"] == pair["window_noops"] == 3
    assert pair["metrics"]["delta"]["point"] == 0
    assert result["paired"]["paraphrase/overall"]["missing_attacks"] == 3
    assert result["paired"]["paraphrase/overall"]["metrics"]["delta"]["point"] is None
    rows[2]["adv_source_id"] = "wrong"
    with pytest.raises(ValueError):
        assemble(rows, scores, groups, draws)


def test_bootstrap_golden_and_malformed_vectors():
    import hashlib
    import json
    import random

    from litmus.evaluation.metrics import validate_draws

    seed = int.from_bytes(
        hashlib.sha256(
            json.dumps(
                ["litmus/r1/bootstrap/v1", 20261030],
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).digest(),
        "big",
    )
    rng = random.Random(seed)
    assert draws_for(["a", "b", "c"])[0] == [rng.randrange(3) for _ in range(3)]
    with pytest.raises(ValueError):
        draws_for(["b", "a"])
    bad = draws_for(["a", "b"])
    bad[0][0] = 3
    with pytest.raises(ValueError):
        validate_draws(["a", "b"], bad)


def test_auc_pairwise_oracle_ties_and_multiplicity():
    samples = [
        (-2.0, False, "a"),
        (0.0, True, "a"),
        (0.0, False, "b"),
        (2.0, True, "b"),
    ]
    weights = {"a": 3, "b": 2}
    pos = [r for r, y, g in samples if y for _ in range(weights[g])]
    neg = [r for r, y, g in samples if not y for _ in range(weights[g])]
    expected = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (
        len(pos) * len(neg)
    )
    assert auc(samples, weights) == expected
    assert auc([(1.0, True, "a"), (1.0, False, "b")], {"a": 2, "b": 3}) == 0.5
    assert auc([(0.0, True, "a"), (1.0, False, "b")], weights) == 0.0
    assert auc([(1.0, True, "a")], weights) is None


def test_fixed_rates_and_paired_delta_use_same_arms():
    assert rate([(True, "a"), (False, "b")], {"a": 3, "b": 1}) == 0.75
    assert rate([], {}) is None
    result = paired([(True, False, "a"), (False, True, "b")], {"a": 3, "b": 1})
    assert result == {
        "clean_rate": 0.75,
        "attack_rate": 0.25,
        "delta": -0.5,
        "both": 0,
        "neither": 0,
        "clean_only": 3,
        "attack_only": 1,
        "pairs": 4,
    }


def test_draws_deterministic_shared_and_not_deduplicated():
    first = draws_for(["a", "b", "c"])
    assert first == draws_for(["a", "b", "c"]) and len(first) == 1000
    assert all(
        len(row) == 3 and all(type(i) is int and 0 <= i < 3 for i in row)
        for row in first
    )
    assert any(len(set(row)) < 3 for row in first)
    assert all(sum(Counter(row).values()) == 3 for row in first)


def test_interval_boundaries_undefined_and_nearest_rank():
    good = list(map(float, range(1000)))
    assert interval(good, True)["ci"] == [24.0, 974.0]
    assert interval([None] * 50 + good[:950], True)["defined_replicates"] == 950
    assert interval([None] * 50 + good[:950], True)["ci"] is not None
    assert (
        interval([None] * 51 + good[:949], True)["status"]
        == "interval not reported (unstable resampling)"
    )
    assert interval(good, False)["status"] == "insufficient data; no interval"
