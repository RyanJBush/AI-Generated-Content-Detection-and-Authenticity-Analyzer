"""Scorer math (Addendum A4) against hand-computed vectors and a scalar oracle.

Hand-computed vectors are ported from the retired tests
(litmus-text-before-multimodal-2026-10-26 = 106a645,
tests/test_binoculars_math.py), restricted to batch size 1.

Tolerances (scorer is float32; the oracle is float64):
- Hand vectors: logits are logs of powers of 2, so every statistic is a
  rational multiple of ln 2; the only error is float32 rounding of ~4-term
  sums of O(1) values, i.e. a few ulps of 1.19e-7. ABS_TOL_HAND = 1e-6.
- Oracle comparison: REL_TOL = 1e-5, ABS_TOL = 1e-6. float32 has unit roundoff
  u = 2**-24 = 5.96e-8. log_softmax and the per-position sum over V <= 1000
  terms accumulate a relative error bounded by about V*u = 6e-5 in the worst
  case for naive summation, but torch uses pairwise/vectorized reductions
  (error ~ log2(V)*u = 6e-7); means over T and one division add a few u.
  1e-5 is ~15x the pairwise bound while still far below the differences the
  role-swap and final-position tests rely on (>= 4e-3 absolute on B ~ 0.9).
"""
import math
import random

import pytest
import torch
from binoculars_oracle import oracle

from litmus.scorer.binoculars import (
    NumericalScoringError,
    binoculars_statistics,
    validate_statistics,
)

LN2 = math.log(2)
ABS_TOL_HAND = 1e-6
REL_TOL = 1e-5
ABS_TOL = 1e-6

# Distributions over a 4-token vocabulary, with -log2 p on the right
pA = [1 / 2, 1 / 4, 1 / 8, 1 / 8]  # bits [1, 2, 3, 3]
pB = [1 / 4, 1 / 4, 1 / 4, 1 / 4]  # bits [2, 2, 2, 2]
pC = [1 / 8, 1 / 8, 1 / 4, 1 / 2]  # bits [3, 3, 2, 1]
pD = [1 / 4, 1 / 2, 1 / 8, 1 / 8]  # bits [2, 1, 3, 3]

# Main fixture, T = 4; row t predicts ids[t+1]
PERFORMER = [pA, pB, pC, pD]
OBSERVER = [pB, pC, pA, pB]
IDS = [1, 0, 3, 1]
# NLL_perf: targets 0, 3, 1 at rows 0..2: pA[0]=1, pB[3]=2, pC[1]=3 bits -> 2 bits
NLL_PERF = 2 * LN2
# XENT rows: pB.[1,2,3,3]=9/4, pC.[2,2,2,2]=2, pA.[3,3,2,1]=21/8, pB.[2,1,3,3]=9/4
#   mean over all 4 rows = 73/32 bits (excluding the final row: 55/24 bits)
XENT = 73 / 32 * LN2
SCORE = 2 / (73 / 32)
# Roles swapped: NLL = observer targets pB[0]=2, pC[3]=1, pA[1]=2 -> 5/3 bits;
#   XENT rows pA.[2,2,2,2]=2, pB.[3,3,2,1]=9/4, pC.[1,2,3,3]=21/8,
#   pD.[2,2,2,2]=2 -> 71/32 bits
SWAPPED_NLL = 5 / 3 * LN2
SWAPPED_XENT = 71 / 32 * LN2
SWAPPED_SCORE = (5 / 3) / (71 / 32)


def logits(rows):
    return torch.log(torch.tensor(rows, dtype=torch.float32))


def stats_of(obs_rows, perf_rows, ids):
    return binoculars_statistics(logits(obs_rows), logits(perf_rows),
                                 torch.tensor(ids))


def close(actual, expected, tol=ABS_TOL_HAND):
    assert abs(actual - expected) < tol, (actual, expected)


# --- hand-computed vectors (ported) ---

def test_hand_computed_values():
    out = stats_of(OBSERVER, PERFORMER, IDS)
    close(out["nll_performer"], NLL_PERF)
    close(out["xent"], XENT)
    close(out["score"], SCORE)
    assert out["n_input_tokens"] == 4 and out["n_target_tokens"] == 3


def test_hand_computed_values_match_oracle():
    ref = oracle(logits(OBSERVER).tolist(), logits(PERFORMER).tolist(), IDS)
    close(ref["nll_performer"], NLL_PERF)
    close(ref["xent"], XENT)
    close(ref["score"], SCORE)


def test_roles_are_asymmetric():
    swapped = stats_of(PERFORMER, OBSERVER, IDS)
    close(swapped["nll_performer"], SWAPPED_NLL)
    close(swapped["xent"], SWAPPED_XENT)
    close(swapped["score"], SWAPPED_SCORE)
    assert abs(swapped["score"] - SCORE) > 1e-2


def test_first_token_is_not_a_target_and_last_token_is():
    base = stats_of(OBSERVER, PERFORMER, IDS)
    out = stats_of(OBSERVER, PERFORMER, [2, 0, 3, 1])
    close(out["nll_performer"], NLL_PERF)
    # Last target becomes -log2 pC[2] = 2 bits -> (1 + 2 + 2) / 3
    out = stats_of(OBSERVER, PERFORMER, [1, 0, 3, 2])
    close(out["nll_performer"], 5 / 3 * LN2)
    close(out["xent"], base["xent"])


def test_final_position_in_denominator_not_numerator():
    # Rows 0-1 uniform for both (2 bits each); final row observer pA,
    # performer pC: pA.[3,3,2,1] = 21/8 bits -> XENT = (2 + 2 + 21/8)/3 = 53/24
    out = stats_of([pB, pB, pA], [pB, pB, pC], [0, 1, 2])
    close(out["xent"], 53 / 24 * LN2)
    close(out["nll_performer"], 2 * LN2)
    # Changing only the final performer row changes XENT only:
    # pA.[2,1,3,3] = 2 bits -> XENT 2 bits
    out2 = stats_of([pB, pB, pA], [pB, pB, pD], [0, 1, 2])
    close(out2["nll_performer"], 2 * LN2)
    close(out2["xent"], 2 * LN2)


def test_excluding_final_position_changes_score():
    full = stats_of(OBSERVER, PERFORMER, IDS)
    # XENT over rows 0..T-2 only (the wrong convention) = 55/24 bits
    o = torch.log_softmax(logits(OBSERVER), -1)
    p = torch.log_softmax(logits(PERFORMER), -1)
    xent_wrong = float((-(o[:-1].exp() * p[:-1]).sum(-1)).mean())
    close(xent_wrong, 55 / 24 * LN2)
    # B with the final position excluded = 2 / (55/24) = 48/55, versus 64/73
    wrong_score = full["nll_performer"] / xent_wrong
    close(wrong_score, 48 / 55)
    close(full["score"], 64 / 73)
    assert abs(48 / 55 - 64 / 73) > 1000 * ABS_TOL_HAND  # 0.0040 apart


# --- seeded random logits vs the scalar oracle ---

CASES = [(v, t) for v in (2, 7, 50, 1000) for t in (2, 3, 17, 64)]


@pytest.mark.parametrize("vocab, length", CASES)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_matches_scalar_oracle(vocab, length, seed):
    rng = random.Random(f"{seed}-{vocab}-{length}")
    obs = [[rng.gauss(0, 3) for _ in range(vocab)] for _ in range(length)]
    perf = [[rng.gauss(0, 3) for _ in range(vocab)] for _ in range(length)]
    ids = [rng.randrange(vocab) for _ in range(length)]

    got = binoculars_statistics(torch.tensor(obs), torch.tensor(perf),
                                torch.tensor(ids))
    ref = oracle(obs, perf, ids)
    for key in ("nll_performer", "xent", "score"):
        assert math.isclose(got[key], ref[key], rel_tol=REL_TOL, abs_tol=ABS_TOL), (
            key, got[key], ref[key])


def test_oracle_role_swap_and_final_position_differ():
    rng = random.Random("oracle-structure")
    obs = [[rng.gauss(0, 3) for _ in range(9)] for _ in range(5)]
    perf = [[rng.gauss(0, 3) for _ in range(9)] for _ in range(5)]
    ids = [rng.randrange(9) for _ in range(5)]
    base = oracle(obs, perf, ids)
    assert abs(oracle(perf, obs, ids)["score"] - base["score"]) > 1e-3
    got = binoculars_statistics(torch.tensor(perf), torch.tensor(obs),
                                torch.tensor(ids))
    assert math.isclose(got["score"], oracle(perf, obs, ids)["score"],
                        rel_tol=REL_TOL, abs_tol=ABS_TOL)


# --- validation guards ---

@pytest.mark.parametrize("case", ["shape_mismatch", "single_token",
                                  "id_out_of_range", "ids_length"])
def test_invalid_inputs_raise(case):
    obs, perf, ids = logits(OBSERVER), logits(PERFORMER), torch.tensor(IDS)
    if case == "shape_mismatch":
        perf = torch.cat([perf, perf[..., :1]], dim=-1)
    elif case == "single_token":
        obs, perf, ids = obs[:1], perf[:1], ids[:1]
    elif case == "id_out_of_range":
        ids = torch.tensor([1, 0, 4, 1])
    elif case == "ids_length":
        ids = torch.tensor([1, 0, 3])
    with pytest.raises(ValueError):
        binoculars_statistics(obs, perf, ids)


def test_nan_logits_raise_naming_quantity():
    obs, perf = logits(OBSERVER), logits(PERFORMER)
    perf[1, 2] = float("nan")
    with pytest.raises(NumericalScoringError, match=r"nll_performer is not finite"):
        binoculars_statistics(obs, perf, torch.tensor(IDS))


def test_zero_xent_raises():
    # exp(-200) underflows to 0 in float32: all observer mass where the
    # performer log-prob is 0, so every row's XENT is exactly 0
    row = [0.0, -200.0, -200.0, -200.0]
    t = torch.tensor([row] * 4)
    with pytest.raises(NumericalScoringError, match=r"xent must be > 0, got 0.0"):
        binoculars_statistics(t, t.clone(), torch.tensor([0, 0, 0, 0]))


@pytest.mark.parametrize("overrides, message", [
    ({"nll_performer": -1e-3}, r"nll_performer must be >= 0"),
    ({"xent": 0.0}, r"xent must be > 0"),
    ({"xent": -0.5}, r"xent must be > 0"),
    ({"nll_performer": float("inf")}, r"nll_performer is not finite"),
    ({"score": float("nan")}, r"score is not finite"),
])
def test_validator_rejects(overrides, message):
    stats = {"nll_performer": 1.0, "xent": 1.0, "score": 1.0}
    stats.update(overrides)
    with pytest.raises(NumericalScoringError, match=message):
        validate_statistics(stats)


def test_reductions_are_float32_for_low_precision_logits():
    obs, perf = logits(OBSERVER), logits(PERFORMER)
    low = binoculars_statistics(obs.to(torch.bfloat16), perf.to(torch.bfloat16),
                                torch.tensor(IDS))
    ref = binoculars_statistics(obs.to(torch.bfloat16).float(),
                                perf.to(torch.bfloat16).float(), torch.tensor(IDS))
    assert low == ref
