"""Production text evidence with validated, exact-profile R1-F calibration.

Without a valid exact calibration the result stays inconclusive. CPU and
incomplete profiles never apply calibration; effective-setting drift gives no score.
"""

import pathlib
from typing import Any, Dict, Optional

from litmus import config
from litmus.schemas import Calibration, OriginEvidence, OriginResult
from litmus.scorer.calibration import (
    CalibrationError,
    find_calibration,
    orient,
    validate_score_statistics,
)
from litmus.scorer.identity import PROFILE_FIELDS
from litmus.scorer.loader import CUDA_ORDER_REASON, profile_failures

METHOD_ID = "binoculars"
NO_CALIBRATION = "no calibration for this configuration"
PROFILE_INCOMPLETE = "execution_profile_incomplete"
PROFILE_CHANGED = "execution_profile_changed"
CALIBRATION_APPLIED = "calibration_applied"
CALIBRATION_INVALID = "calibration_invalid"
TOO_SHORT = "too_short"
NO_NONWHITESPACE = "no_nonwhitespace_content"

BASE_LIMITATIONS = [
    "raw_score is a score, not a probability",
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


def calibration_reason(
    profile: Dict[str, Any],
    config_hash: Optional[str],
    calibrations_dir: Optional[pathlib.Path] = None,
    failures: Optional[Dict[str, str]] = None,
) -> str:
    """Profile/exact-artifact lookup status (kept for model-free diagnostics)."""
    return _resolve_calibration(profile, config_hash, calibrations_dir, failures)[0]


def _resolve_calibration(profile, config_hash, calibrations_dir, failures):
    if failures is None:
        failures = profile_failures(profile)
    if failures:
        return PROFILE_INCOMPLETE, None, None
    if profile.get("device_type") != "cuda":
        return NO_CALIBRATION, None, None
    try:
        found = find_calibration(config_hash, calibrations_dir)
    except CalibrationError as error:
        return CALIBRATION_INVALID, None, str(error)
    if found is None:
        return NO_CALIBRATION, None, None
    return CALIBRATION_APPLIED, found, None


def evidence_from_score(
    stats: Dict[str, Any],
    scored_window: Dict[str, Any],
    profile: Dict[str, Any],
    fields: Optional[Dict[str, Any]],
    config_hash: Optional[str],
    tokenizer_vocab_size: int,
    model_output_dim: int,
    calibrations_dir: Optional[pathlib.Path] = None,
    failures: Optional[Dict[str, str]] = None,
    apply_calibration: bool = True,
) -> OriginEvidence:
    try:
        validate_score_statistics(stats)
    except CalibrationError as error:
        return _evidence(
            OriginResult.ERROR,
            ["numerical_error: " + str(error)],
            details={"scored_window": scored_window},
        )
    if failures is None:
        failures = profile_failures(profile)
    reason, artifact, lookup_error = (
        _resolve_calibration(profile, config_hash, calibrations_dir, failures)
        if apply_calibration
        else ("calibration_disabled_for_creation", None, None)
    )
    reasons = [reason]
    if failures.get("cuda_initialized_before_settings") == CUDA_ORDER_REASON:
        reasons.append(CUDA_ORDER_REASON)
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
        "execution_profile_complete": not failures,
        "execution_profile_failures": failures,
    }
    extra = (
        ["only the first 512 tokens were scored"] if scored_window["truncated"] else []
    )
    evidence = _evidence(
        OriginResult.INCONCLUSIVE,
        reasons,
        raw_score=stats["score"],
        details=details,
        extra_limitations=extra,
    )
    if lookup_error:
        evidence.details["calibration_error"] = lookup_error
    if reason == CALIBRATION_APPLIED:
        try:
            if artifact is None or artifact["payload"]["scoring_config"] != fields:
                raise CalibrationError("calibration_runtime_fields_mismatch")
            if any(fields[key] != profile[key] for key in PROFILE_FIELDS):
                raise CalibrationError("calibration_runtime_profile_mismatch")
            p = artifact["payload"]
            positive = orient(stats["score"], p["score_direction"]) > p["threshold_c"]
            evidence.result = (
                OriginResult.SUPPORTS_AI if positive else OriginResult.NO_SIGNAL
            )
            evidence.reasons = [
                "above_calibrated_threshold"
                if positive
                else "not_above_calibrated_threshold"
            ]
            evidence.calibration = Calibration(
                config_hash,
                p["dev_set_id"],
                p["alpha"],
                p["threshold_c"],
                p["n_dev_negatives"],
                artifact["created"],
            )
            evidence.details["calibration_artifact_sha256"] = artifact[
                "artifact_sha256"
            ]
            evidence.details["calibration_procedure"] = {
                k: p[k]
                for k in (
                    "procedure",
                    "transform",
                    "comparison",
                    "above",
                    "ties",
                    "score_direction",
                )
            }
            evidence.limitations.append(
                "5% is an empirical development operating point, "
                "not a guaranteed population false-positive rate"
            )
        except CalibrationError as error:
            evidence.reasons = [CALIBRATION_INVALID]
            evidence.details["calibration_error"] = str(error)
    return evidence


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

    def score_text(self, pair, text: str, *, apply_calibration=True) -> OriginEvidence:
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
        from litmus.scorer.loader import (
            effective_settings,
            forward_logits,
            profile_changes,
        )
        from litmus.scorer.tokenize import tokenize_window

        window = tokenize_window(pair.tokenizer, text)
        if window.tokens_scored < config.MIN_TOKENS:
            return _evidence(
                OriginResult.INCONCLUSIVE,
                [TOO_SHORT],
                details={"scored_window": window.scored_window()},
            )

        import torch

        # Re-read immediately before scoring; never re-apply (that would hide
        # a change). Any difference from the hashed profile -> no score.
        changes = profile_changes(
            pair.profile,
            effective_settings(torch, pair.device.type, pair.observer, pair.performer),
        )
        if changes:
            return _evidence(
                OriginResult.INCONCLUSIVE,
                [PROFILE_CHANGED],
                details={
                    "scored_window": window.scored_window(),
                    "execution_profile_changes": changes,
                },
            )
        obs = forward_logits(torch, pair.observer, window.ids, pair.device)
        perf = forward_logits(torch, pair.performer, window.ids, pair.device)
        ids = torch.tensor(window.ids, device=pair.device)
        try:
            stats = binoculars_statistics(obs, perf, ids)
        except NumericalScoringError as e:
            return _evidence(
                OriginResult.ERROR,
                [f"numerical_error: {e}"],
                details={"scored_window": window.scored_window()},
            )

        failures = profile_failures(
            pair.profile,
            models=(("observer", pair.observer), ("performer", pair.performer)),
        )
        try:
            fields = config_fields(
                pair.profile,
                static_fields(pair.tokenizer_json_sha256),
                list(SOURCE_FILES),
                source_sha256(),
            )
            config_hash = scoring_config_hash(fields)
        except (KeyError, ValueError):
            if not failures:
                raise
            fields = config_hash = None  # incomplete profile: nothing to match
        return evidence_from_score(
            stats,
            window.scored_window(),
            pair.profile,
            fields,
            config_hash,
            pair.tokenizer_vocab_size,
            pair.model_output_dim,
            self.calibrations_dir,
            failures,
            apply_calibration,
        )
