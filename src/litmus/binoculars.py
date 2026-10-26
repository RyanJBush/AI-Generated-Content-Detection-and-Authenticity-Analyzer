"""Layer A: Binoculars statistics from observer/performer logits (SPEC §3.1).

Pure tensor math; no model loading. Roles: observer = base model, performer = instruct model.
"""
import math

import torch


def binoculars_statistics(observer_logits, performer_logits, input_ids, attention_mask):
    """Per-document Binoculars statistics for a right-padded batch.

    Args:
        observer_logits, performer_logits: [B, T, V] logits; position t predicts token t+1.
            V is the full model output dimension and is never trimmed.
        input_ids: [B, T] token IDs.
        attention_mask: [B, T] of 0/1, right-padded (no real token after a pad).

    Returns a dict of [B] tensors:
        nll_performer: mean -log P_t[x_{t+1}] over t with m_t = a_t * a_{t+1} (numerator).
        nll_observer: same targets under the observer (baseline only).
        xent: mean over all real positions t (a_t = 1, final real position included) of
            sum_v exp(O_t[v]) * -P_t[v].
        score: nll_performer / xent.
        n_input_tokens: sum_t a_t (denominator count).
        n_scored_tokens: sum_t m_t (numerator count).
    All floating outputs are float32, as are the log-softmax and reductions, regardless of logit dtype.

    Raises NumericalScoringError if any document's statistics fail validate_statistics.
    """
    if observer_logits.dim() != 3 or observer_logits.shape != performer_logits.shape:
        raise ValueError(
            f"observer/performer logits must share shape [B, T, V]; got "
            f"{tuple(observer_logits.shape)} and {tuple(performer_logits.shape)}"
        )
    if input_ids.shape != observer_logits.shape[:2] or attention_mask.shape != input_ids.shape:
        raise ValueError(
            f"input_ids {tuple(input_ids.shape)} and attention_mask {tuple(attention_mask.shape)} "
            f"must match logits batch/sequence dims {tuple(observer_logits.shape[:2])}"
        )
    vocab = observer_logits.shape[-1]
    if input_ids.min() < 0 or input_ids.max() >= vocab:
        raise ValueError(f"input_ids outside output dimension {vocab}")

    a = attention_mask.bool()
    if (attention_mask != a.to(attention_mask.dtype)).any():
        raise ValueError("attention_mask must contain only 0 and 1")
    if (a[:, 1:] & ~a[:, :-1]).any():
        raise ValueError("attention_mask must be right-padded")

    o = torch.log_softmax(observer_logits.float(), dim=-1)
    p = torch.log_softmax(performer_logits.float(), dim=-1)

    # Numerator: logits at t (1..T-1) score the next input token x_{t+1}.
    m = a[:, :-1] & a[:, 1:]
    targets = input_ids[:, 1:].unsqueeze(-1)
    zero = torch.zeros((), dtype=torch.float32, device=o.device)
    perf_target_nll = torch.where(m, -p[:, :-1].gather(-1, targets).squeeze(-1), zero)
    obs_target_nll = torch.where(m, -o[:, :-1].gather(-1, targets).squeeze(-1), zero)

    # Denominator: observer-to-performer cross-entropy at every real position, including the last.
    position_xent = torch.where(a, -(o.exp() * p).sum(dim=-1), zero)

    n_scored = m.sum(dim=-1)
    n_input = a.sum(dim=-1)
    if (n_scored == 0).any():
        raise ValueError("every document needs at least 2 real tokens")

    nll_performer = perf_target_nll.sum(dim=-1) / n_scored
    nll_observer = obs_target_nll.sum(dim=-1) / n_scored
    xent = position_xent.sum(dim=-1) / n_input
    stats = {
        "nll_performer": nll_performer,
        "nll_observer": nll_observer,
        "xent": xent,
        "score": nll_performer / xent,
        "n_input_tokens": n_input,
        "n_scored_tokens": n_scored,
    }
    validate_statistics(stats)
    return stats


class NumericalScoringError(ValueError):
    """A computed statistic is invalid; no score is returned."""


def validate_statistics(stats):
    """Raise NumericalScoringError unless, for every document, NLL_perf and NLL_obs are finite and >= 0,
    XENT is finite and > 0, and B is finite."""
    checks = [
        ("nll_performer", lambda v: v >= 0, ">= 0"),
        ("nll_observer", lambda v: v >= 0, ">= 0"),
        ("xent", lambda v: v > 0, "> 0"),
        ("score", lambda v: True, None),
    ]
    for name, ok, requirement in checks:
        for i, value in enumerate(stats[name].tolist()):
            if not math.isfinite(value):
                raise NumericalScoringError(f"{name} is not finite ({value}) for document {i}")
            if not ok(value):
                raise NumericalScoringError(f"{name} must be {requirement}, got {value} for document {i}")
