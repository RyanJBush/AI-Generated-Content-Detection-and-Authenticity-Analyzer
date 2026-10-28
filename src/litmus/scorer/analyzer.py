"""Text origin analyzer emitting uncalibrated OriginEvidence (R1-B1).

Result is always ``inconclusive`` in R1-B1: either no calibration exists for
the exact configuration, the execution profile is incomplete (CA2), or the
run is on CPU (always uncalibrated). Threshold application is R1-F.
"""
import pathlib
from typing import Any, Dict, Optional

from litmus import config
from litmus.schemas import OriginEvidence, OriginResult
from litmus.scorer.calibration import find_calibration
from litmus.scorer.loader import profile_is_complete

METHOD_ID = "binoculars"
NO_CALIBRATION = "no calibration for this configuration"
PROFILE_INCOMPLETE = "execution_profile_incomplete"
CALIBRATION_NOT_APPLIED = "calibration_application_not_implemented"
TOO_SHORT = "too_short"
NO_NONWHITESPACE = "no_nonwhitespace_content"

BASE_LIMITATIONS = [
    "raw_score is an uncalibrated score, not a probability",
    "absence of evidence is not evidence of human origin",
]


def _evidence(result, reasons, raw_score=None, details=None, extra_limitations=()):
    return OriginEvidence(
        method_id=METHOD_ID,
        method_version=config.SCORER_VERSION,
        result=result,
        raw_score=raw_score,
        score_direction=config.SCORE_DIRECTION if raw_score is not None else None,
        calibration=None,
        reasons=list(reasons),
        limitations=BASE_LIMITATIONS + list(extra_limitations),
        details=details or {},
    )


def calibration_reason(profile: Dict[str, Any], config_hash: str,
                       calibrations_dir: Optional[pathlib.Path] = None) -> str:
    """Why the result is inconclusive; strict exact-hash lookup."""
    if not profile_is_complete(profile):
        return PROFILE_INCOMPLETE  # CA2: never matches any calibration
    if profile.get("device_type") != "cuda":
        return NO_CALIBRATION  # CPU runs are always uncalibrated in R1
    if find_calibration(config_hash, calibrations_dir) is None:
        return NO_CALIBRATION
    return CALIBRATION_NOT_APPLIED  # R1-F applies thresholds; not R1-B1


def evidence_from_score(stats: Dict[str, Any], scored_window: Dict[str, Any],
                        profile: Dict[str, Any], fields: Dict[str, Any],
                        config_hash: str, tokenizer_vocab_size: int,
                        model_output_dim: int,
                        calibrations_dir: Optional[pathlib.Path] = None
                        ) -> OriginEvidence:
    reason = calibration_reason(profile, config_hash, calibrations_dir)
    details = {
        "scored_window": scored_window,
        "nll_performer": stats["nll_performer"],
        "xent": stats["xent"],
        "n_input_tokens": stats["n_input_tokens"],
        "n_target_tokens": stats["n_target_tokens"],
        "tokenizer_vocab_size": tokenizer_vocab_size,
        "model_output_dim": model_output_dim,
        "scoring_config_hash": config_hash,
        "scoring_config": fields,
        "execution_profile_complete": profile_is_complete(profile),
    }
    extra = (["only the first 512 tokens were scored"]
             if scored_window["truncated"] else [])
    return _evidence(OriginResult.INCONCLUSIVE, [reason], raw_score=stats["score"],
                     details=details, extra_limitations=extra)


class BinocularsAnalyzer:
    """Callable text -> OriginEvidence; loads the model pair on first use."""

    def __init__(self, models_dir=None, device=None, calibrations_dir=None):
        self.models_dir = models_dir
        self.device = device
        self.calibrations_dir = calibrations_dir
        self._pair = None

    def _load(self):
        if self._pair is None:
            from litmus.scorer.loader import load_pair
            self._pair = load_pair(self.models_dir, self.device)
        return self._pair

    def __call__(self, text: str) -> OriginEvidence:
        from litmus.scorer.loader import ModelNotInstalled

        if not text.strip():
            # Addendum B2
            return _evidence(OriginResult.INCONCLUSIVE, [NO_NONWHITESPACE])
        try:
            pair = self._load()
        except ModelNotInstalled as e:
            return _evidence(OriginResult.ERROR, [str(e)])
        return self.score_text(pair, text)

    def score_text(self, pair, text: str) -> OriginEvidence:
        from litmus.scorer.binoculars import (
            NumericalScoringError,
            binoculars_statistics,
        )
        from litmus.scorer.identity import (
            SOURCE_FILES,
            config_fields,
            scoring_config_hash,
            source_sha256,
            static_fields,
        )
        from litmus.scorer.loader import apply_numerical_settings, forward_logits
        from litmus.scorer.tokenize import tokenize_window

        window = tokenize_window(pair.tokenizer, text)
        if window.tokens_scored < config.MIN_TOKENS:
            return _evidence(OriginResult.INCONCLUSIVE, [TOO_SHORT],
                             details={"scored_window": window.scored_window()})

        torch = apply_numerical_settings()
        obs = forward_logits(torch, pair.observer, window.ids, pair.device)
        perf = forward_logits(torch, pair.performer, window.ids, pair.device)
        ids = torch.tensor(window.ids, device=pair.device)
        try:
            stats = binoculars_statistics(obs, perf, ids)
        except NumericalScoringError as e:
            return _evidence(OriginResult.ERROR, [f"numerical_error: {e}"],
                             details={"scored_window": window.scored_window()})

        fields = config_fields(pair.profile, static_fields(pair.tokenizer_json_sha256),
                               list(SOURCE_FILES), source_sha256())
        return evidence_from_score(
            stats, window.scored_window(), pair.profile, fields,
            scoring_config_hash(fields), pair.tokenizer_vocab_size,
            pair.model_output_dim, self.calibrations_dir)
