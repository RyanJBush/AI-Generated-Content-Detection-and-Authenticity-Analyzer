"""Report object (SPEC §3.3; contract: docs/interfaces.md §5)."""
import json

from litmus import config

REPORT_VERSION = "0.3.2"
NOTE = "Score is a ratio of mean negative log-likelihood to cross-entropy, not a probability of AI authorship."
DISCLAIMER = (
    "Litmus reports evidence, not verdicts. The Binoculars score and pattern counts are not proof that a person "
    "used AI and must not be the sole basis for academic, employment, or moderation decisions. Thresholds are "
    "calibrated for one model pair on a development sample; the uncertain band is an abstention policy, not a "
    "confidence measure. Pattern counts are an unvalidated heuristic, and phrases to inspect are not evidence "
    "that a claim is unsupported."
)
FLAG_TEXT = {
    "flagged": "score crossed the strict calibrated threshold",
    "uncertain_abstain": "score fell between the calibrated thresholds; abstaining",
    "not_flagged": "score did not cross the calibrated threshold",
    "no_calibration": "no valid calibration for this scoring configuration; raw score only, no flag",
    "too_short": f"fewer than {config.MIN_INPUT_TOKENS} input tokens; not scored",
}


def decide_flag(score_result, calibration_status):
    """SPEC §3.3 flag policy; None when the score is a numerical error."""
    if score_result.status == "too_short":
        return "too_short"
    if score_result.status == "error":
        return None
    if not calibration_status.valid:
        return "no_calibration"
    if score_result.score < calibration_status.t_strict:
        return "flagged"
    if score_result.score < calibration_status.t_primary:
        return "uncertain_abstain"
    return "not_flagged"


def build_report(text, score_result, slop_result, identity, calibration_status):
    for feature in slop_result["features"].values():
        if any(not 0 <= start <= end <= len(text) for start, end in feature["spans"]):
            raise ValueError("slop span outside the original text")
    flag = decide_flag(score_result, calibration_status)
    calibration = None
    if calibration_status.valid:
        calibration = {
            "artifact_sha256": calibration_status.artifact_sha256,
            "scoring_config_hash": identity["scoring_config_hash"],
            "scoring_identity_hash": identity["scoring_identity_hash"],
            "execution_profile_hash": identity["execution_profile_hash"],
            "t_strict": calibration_status.t_strict,
            "t_primary": calibration_status.t_primary,
            "source": "clean human dev rows",
        }
    scoring_identity = identity["scoring_identity"]
    return {
        "version": REPORT_VERSION,
        "scorer_version": scoring_identity["scorer_version"],
        "preprocessing_version": scoring_identity["preprocessing_version"],
        "scoring_config_hash": identity["scoring_config_hash"],
        "scoring_identity_hash": identity["scoring_identity_hash"],
        "execution_profile_hash": identity["execution_profile_hash"],
        "models": {
            "observer": scoring_identity["observer"],
            "performer": scoring_identity["performer"],
            "tokenizer_sha256": scoring_identity["tokenizer_sha256"],
            "weight_dtype": identity["execution_profile"]["weight_dtype"],
        },
        "n_tokens": score_result.n_tokens,
        "n_input_tokens": score_result.n_input_tokens,
        "n_scored_tokens": score_result.n_scored_tokens,
        "truncated": score_result.truncated,
        "binoculars": {
            "nll_performer": score_result.nll_performer,
            "xent": score_result.xent,
            "score": score_result.score,
            "baselines": {"nll_observer": score_result.nll_observer},
            "flag": flag,
            "flag_text": FLAG_TEXT.get(flag),
            "error": score_result.error,
            "calibration": calibration,
            "calibration_status": {
                "valid": calibration_status.valid,
                "reason": calibration_status.reason,
                "path": calibration_status.path,
            },
            "note": NOTE,
        },
        "slop": slop_result,
        "disclaimer": DISCLAIMER,
    }


def report_to_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
