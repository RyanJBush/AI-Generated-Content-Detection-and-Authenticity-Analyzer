"""Hand-computed tests for litmus.binoculars.binoculars_statistics (SPEC §8.1). No model downloads.

Logits are set to log-probabilities whose values are powers of 2, so log_softmax returns them
unchanged and every statistic is a rational multiple of ln 2, computed by hand below in bits.
"""
import math

import pytest
import torch

from litmus.binoculars import binoculars_statistics

LN2 = math.log(2)

# Distributions over a 4-token vocabulary, with -log2 p shown on the right.
pA = [1 / 2, 1 / 4, 1 / 8, 1 / 8]  # bits [1, 2, 3, 3]
pB = [1 / 4, 1 / 4, 1 / 4, 1 / 4]  # bits [2, 2, 2, 2]
pC = [1 / 8, 1 / 8, 1 / 4, 1 / 2]  # bits [3, 3, 2, 1]
pD = [1 / 4, 1 / 2, 1 / 8, 1 / 8]  # bits [2, 1, 3, 3]

# Main fixture, T = 4. Row t is the distribution at input position t (predicting x_{t+1}).
PERFORMER = [pA, pB, pC, pD]
OBSERVER = [pB, pC, pA, pB]
IDS = [1, 0, 3, 1]

# NLL_perf, targets x2..x4 = 0, 3, 1 at positions 1..3:
#   -log2 pA[0] = 1, -log2 pB[3] = 2, -log2 pC[1] = 3  ->  (1 + 2 + 3) / 3 = 2 bits.
# Misaligned alternatives give different values: P_t[x_t], t=1..3 -> (2+2+1)/3 = 5/3;
#   P_t[x_t], t=2..4 -> (2+1+1)/3 = 4/3.
NLL_PERF = 2 * LN2
# NLL_obs, same targets under the observer: -log2 pB[0] = 2, pC[3] = 1, pA[1] = 2 -> 5/3 bits.
NLL_OBS = 5 / 3 * LN2
# XENT per position, sum_v O_t[v] * (-log2 P_t[v]):
#   t1: pB . [1,2,3,3] = 9/4;  t2: pC . [2,2,2,2] = 2;  t3: pA . [3,3,2,1] = 3/2+3/4+1/4+1/8 = 21/8;
#   t4 (final, no target): pB . [2,1,3,3] = 9/4.
#   Mean over all 4 real positions = (18 + 16 + 21 + 18) / 8 / 4 = 73/32 bits.
#   (Excluding the final position would give 55/24 bits.) Token 2 never appears in IDS but its
#   probability mass still contributes, so the full output dimension is used.
XENT = 73 / 32 * LN2
SCORE = 2 / (73 / 32)  # = 64/73, unitless

# Roles swapped (observer <-> performer):
#   NLL with observer rows as performer = 5/3 bits (as NLL_obs above).
#   XENT per position, P_t . (-log2 O_t): t1: pA . [2,2,2,2] = 2; t2: pB . [3,3,2,1] = 9/4;
#   t3: pC . [1,2,3,3] = 1/8+1/4+3/4+3/2 = 21/8; t4: pD . [2,2,2,2] = 2  ->  71/32 bits.
SWAPPED_NLL = 5 / 3 * LN2
SWAPPED_XENT = 71 / 32 * LN2
SWAPPED_SCORE = (5 / 3) / (71 / 32)

TOL = 1e-5


def logits(rows):
    return torch.log(torch.tensor(rows, dtype=torch.float32))


def batch(*docs):
    """docs: (observer_rows, performer_rows, ids, mask) tuples of equal length T."""
    obs = torch.stack([logits(d[0]) for d in docs])
    perf = torch.stack([logits(d[1]) for d in docs])
    ids = torch.tensor([d[2] for d in docs])
    mask = torch.tensor([d[3] for d in docs])
    return obs, perf, ids, mask


def main_fixture():
    return batch((OBSERVER, PERFORMER, IDS, [1, 1, 1, 1]))


def assert_close(actual, expected):
    assert abs(float(actual) - expected) < TOL, (float(actual), expected)


def test_hand_computed_values():
    out = binoculars_statistics(*main_fixture())
    assert_close(out["nll_performer"][0], NLL_PERF)
    assert_close(out["nll_observer"][0], NLL_OBS)
    assert_close(out["xent"][0], XENT)
    assert_close(out["score"][0], SCORE)
    assert int(out["n_input_tokens"][0]) == 4
    assert int(out["n_scored_tokens"][0]) == 3


def test_roles_are_asymmetric():
    obs, perf, ids, mask = main_fixture()
    swapped = binoculars_statistics(perf, obs, ids, mask)
    assert_close(swapped["nll_performer"][0], SWAPPED_NLL)
    assert_close(swapped["xent"][0], SWAPPED_XENT)
    assert_close(swapped["score"][0], SWAPPED_SCORE)
    # Each term differs from the correct-role value, so a swap in either term is caught.
    assert abs(SWAPPED_NLL - NLL_PERF) > 100 * TOL
    assert abs(SWAPPED_XENT - XENT) > 100 * TOL
    assert abs(SWAPPED_SCORE - SCORE) > 100 * TOL


def test_performer_only_nll_is_numerator_and_observer_nll_independent():
    obs, perf, ids, mask = main_fixture()
    out = binoculars_statistics(obs, perf, ids, mask)
    # Performer-only NLL baseline is the numerator; observer NLL uses the observer's logits only.
    perf_only = binoculars_statistics(perf, perf, ids, mask)
    obs_only = binoculars_statistics(obs, obs, ids, mask)
    assert_close(perf_only["nll_performer"][0], NLL_PERF)
    assert_close(obs_only["nll_performer"][0], NLL_OBS)
    assert_close(out["nll_observer"][0], NLL_OBS)


def test_first_token_is_not_a_target_and_last_token_is():
    obs, perf, ids, mask = main_fixture()
    base = binoculars_statistics(obs, perf, ids, mask)

    first_changed = ids.clone()
    first_changed[0, 0] = 2
    out = binoculars_statistics(obs, perf, first_changed, mask)
    assert_close(out["nll_performer"][0], NLL_PERF)

    last_changed = ids.clone()
    last_changed[0, 3] = 2  # target at position 3 becomes -log2 pC[2] = 2 bits -> (1+2+2)/3
    out = binoculars_statistics(obs, perf, last_changed, mask)
    assert_close(out["nll_performer"][0], 5 / 3 * LN2)
    assert_close(out["xent"][0], float(base["xent"][0]))


def test_final_position_in_denominator_not_numerator():
    # T = 3. Positions 1-2: observer = performer = uniform, XENT 2 bits each.
    # Position 3 (final): observer pA, performer pC, XENT pA . [3,3,2,1] = 21/8 bits.
    # XENT = (2 + 2 + 21/8) / 3 = 53/24 bits. Restricting to numerator positions would give 2 bits.
    # NLL targets x2 = 1, x3 = 2 under uniform rows: 2 bits each -> 2 bits; position 3 has no target.
    obs, perf, ids, mask = batch(([pB, pB, pA], [pB, pB, pC], [0, 1, 2], [1, 1, 1]))
    out = binoculars_statistics(obs, perf, ids, mask)
    assert_close(out["xent"][0], 53 / 24 * LN2)
    assert_close(out["nll_performer"][0], 2 * LN2)
    assert int(out["n_input_tokens"][0]) == 3
    assert int(out["n_scored_tokens"][0]) == 2

    # Changing the final position's performer row changes XENT only.
    obs2, perf2, ids2, mask2 = batch(([pB, pB, pA], [pB, pB, pD], [0, 1, 2], [1, 1, 1]))
    out2 = binoculars_statistics(obs2, perf2, ids2, mask2)
    assert_close(out2["nll_performer"][0], 2 * LN2)
    # pA . [2,1,3,3] = 1 + 1/4 + 3/8 + 3/8 = 2 bits at the final position -> XENT 2 bits.
    assert_close(out2["xent"][0], 2 * LN2)


def test_right_padding_masks_by_attention_mask():
    # Doc 2 is the first 3 tokens of the main fixture plus one pad position. The pad uses token ID 1,
    # which also occurs as real tokens in both docs (including doc 1's final target), and its logits
    # are NaN; the attention mask alone decides what counts.
    pad_row = [float("nan")] * 4
    obs, perf, ids, mask = batch(
        (OBSERVER, PERFORMER, IDS, [1, 1, 1, 1]),
        (OBSERVER[:3] + [pad_row], PERFORMER[:3] + [pad_row], [1, 0, 3, 1], [1, 1, 1, 0]),
    )
    out = binoculars_statistics(obs, perf, ids, mask)

    # Doc 1 unchanged by batching; its target ID 1 (equal to the pad ID) is scored.
    assert_close(out["nll_performer"][0], NLL_PERF)
    assert_close(out["xent"][0], XENT)
    assert int(out["n_scored_tokens"][0]) == 3

    # Doc 2 by hand: NLL targets 0, 3 -> (1 + 2) / 2 = 3/2 bits; XENT (9/4 + 2 + 21/8) / 3 = 55/24 bits.
    assert_close(out["nll_performer"][1], 3 / 2 * LN2)
    assert_close(out["xent"][1], 55 / 24 * LN2)
    assert_close(out["score"][1], (3 / 2) / (55 / 24))
    assert int(out["n_input_tokens"][1]) == 3
    assert int(out["n_scored_tokens"][1]) == 2

    # Same as scoring doc 2 unpadded on its own.
    alone = binoculars_statistics(*batch((OBSERVER[:3], PERFORMER[:3], [1, 0, 3], [1, 1, 1])))
    for key in ["nll_performer", "nll_observer", "xent", "score"]:
        assert_close(out[key][1], float(alone[key][0]))


def test_reductions_are_float32_for_low_precision_logits():
    obs, perf, ids, mask = main_fixture()
    out = binoculars_statistics(obs.to(torch.bfloat16), perf.to(torch.bfloat16), ids, mask)
    reference = binoculars_statistics(
        obs.to(torch.bfloat16).float(), perf.to(torch.bfloat16).float(), ids, mask
    )
    for key in ["nll_performer", "nll_observer", "xent", "score"]:
        assert out[key].dtype == torch.float32
        assert torch.equal(out[key], reference[key])


@pytest.mark.parametrize(
    "case",
    ["left_padding", "shape_mismatch", "single_token", "id_out_of_range", "non_binary_mask"],
)
def test_invalid_inputs_raise(case):
    obs, perf, ids, mask = main_fixture()
    if case == "left_padding":
        mask = torch.tensor([[0, 1, 1, 1]])
    elif case == "shape_mismatch":
        perf = torch.cat([perf, perf[..., :1]], dim=-1)
    elif case == "single_token":
        mask = torch.tensor([[1, 0, 0, 0]])
    elif case == "id_out_of_range":
        ids = torch.tensor([[1, 0, 4, 1]])
    elif case == "non_binary_mask":
        mask = torch.tensor([[1, 1, 2, 1]])
    with pytest.raises(ValueError):
        binoculars_statistics(obs, perf, ids, mask)
