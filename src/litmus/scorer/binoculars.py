"""Binoculars statistics from observer/performer logits (Addendum A4).

Batch size 1, no padding. Ported from the retired implementation
(litmus-text-before-multimodal-2026-10-26 = 106a645, src/litmus/binoculars.py)
with the batch/attention-mask handling removed, since A4 fixes batch size 1.
"""
import math
from typing import Dict

import torch


class NumericalScoringError(ValueError):
    """A computed statistic is invalid; no score is returned."""


def binoculars_statistics(
    observer_logits: torch.Tensor,
    performer_logits: torch.Tensor,
    ids: torch.Tensor,
) -> Dict[str, float]:
    """Statistics for one document.

    Args:
        observer_logits, performer_logits: [T, V] logits; row t predicts ids[t+1].
            V is the full model output dimension and is never trimmed.
        ids: [T] token IDs, T >= 2.

    Returns floats: nll_performer, xent, score (= nll_performer / xent),
    n_input_tokens (T) and n_target_tokens (T - 1). log_softmax and all
    reductions are float32 regardless of the logit dtype.

    Raises NumericalScoringError naming the failing quantity if any value is
    non-finite, nll_performer < 0, or xent <= 0. No substitute is returned.
    """
    if observer_logits.dim() != 2 or observer_logits.shape != performer_logits.shape:
        raise ValueError(
            f"observer/performer logits must share shape [T, V]; got "
            f"{tuple(observer_logits.shape)} and {tuple(performer_logits.shape)}"
        )
    t_len, vocab = observer_logits.shape
    if ids.dim() != 1 or ids.shape[0] != t_len:
        raise ValueError(f"ids shape {tuple(ids.shape)} must be [{t_len}]")
    if t_len < 2:
        raise ValueError("at least 2 tokens are required")
    if int(ids.min()) < 0 or int(ids.max()) >= vocab:
        raise ValueError(f"ids outside output dimension {vocab}")

    o = torch.log_softmax(observer_logits.float(), dim=-1)
    p = torch.log_softmax(performer_logits.float(), dim=-1)

    # Numerator: row t (0..T-2) scores the next token ids[t+1]
    targets = ids[1:].to(p.device).unsqueeze(-1)
    nll_performer = (-p[:-1].gather(-1, targets).squeeze(-1)).mean()

    # Denominator: observer-to-performer cross-entropy at every position,
    # including the final one (which has no target)
    xent = (-(o.exp() * p).sum(dim=-1)).mean()

    stats = {
        "nll_performer": float(nll_performer),
        "xent": float(xent),
        "score": float(nll_performer / xent),
        "n_input_tokens": t_len,
        "n_target_tokens": t_len - 1,
    }
    validate_statistics(stats)
    return stats


def validate_statistics(stats: Dict[str, float]) -> None:
    """Require finite values, nll_performer >= 0, xent > 0, and a finite score."""
    checks = [
        ("nll_performer", lambda v: v >= 0, ">= 0"),
        ("xent", lambda v: v > 0, "> 0"),
        ("score", lambda v: True, None),
    ]
    for name, ok, requirement in checks:
        value = stats[name]
        if not math.isfinite(value):
            raise NumericalScoringError(f"{name} is not finite ({value})")
        if not ok(value):
            raise NumericalScoringError(f"{name} must be {requirement}, got {value}")
