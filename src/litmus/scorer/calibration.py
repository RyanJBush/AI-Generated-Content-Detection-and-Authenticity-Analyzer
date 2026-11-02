"""Exact R1 5% calibration, artifact and one-way freeze validation."""

import datetime
import hashlib
import json
import math
import pathlib
import re
import struct

from litmus.scorer.identity import (
    PROFILE_FIELDS,
    SOURCE_FIELDS,
    STATIC_FIELDS,
    canonical_json,
    scoring_config_hash,
)
from litmus.scorer.loader import profile_failures

SCHEMA = "r1f-calibration-v1"
PROCEDURE = "distinct-negative-strict-5pct-v1"
DIGEST = re.compile(r"[0-9a-f]{64}")
DIRECTIONS = {
    "lower_means_more_machine": "negate_raw",
    "higher_means_more_machine": "identity",
}
BINDINGS = {
    "dev_set_id",
    "prepared_manifest_sha256",
    "reconciliation_sha256",
    "scores_sha256",
}
ARTIFACT_KEYS = BINDINGS | {
    "schema_version",
    "procedure",
    "alpha",
    "alpha_numerator",
    "alpha_denominator",
    "scoring_config",
    "scoring_config_hash",
    "score_direction",
    "transform",
    "comparison",
    "threshold_c",
    "n_dev_negatives",
    "above",
    "ties",
    "source_run_id",
    "failed_negatives",
}


class CalibrationError(ValueError):
    """Invalid or incomplete calibration/freeze; no threshold may be applied."""


def require(condition, reason):
    if not condition:
        raise CalibrationError(reason)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def envelope(payload, digest_key, **metadata):
    try:
        return {
            "payload": payload,
            digest_key: sha(canonical_json(payload)),
            **metadata,
        }
    except (ValueError, TypeError) as error:
        raise CalibrationError("invalid_canonical_payload") from error


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def invalid(value):
        raise CalibrationError("nonfinite_json:" + value)

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, TypeError) as error:
        raise CalibrationError("invalid_json:" + str(error)) from error
    require(isinstance(value, dict), "json_object_required")
    return value


def orient(raw, direction):
    require(finite(raw), "invalid_score")
    require(direction in DIRECTIONS, "unknown_score_direction")
    return -raw if direction == "lower_means_more_machine" else raw


def select_threshold(oriented_scores, alpha=0.05):
    scores = list(oriented_scores)
    require(type(alpha) is float and alpha == 0.05, "only_5pct_enabled")
    require(len(scores) >= 200, "insufficient_development_negatives")
    require(all(finite(v) for v in scores), "invalid_negative_score")
    for candidate in sorted(set(scores)):
        above = sum(value > candidate for value in scores)
        if 20 * above <= len(scores):
            return {
                "threshold_c": candidate,
                "n_dev_negatives": len(scores),
                "above": above,
                "ties": scores.count(candidate),
            }
    raise CalibrationError("no_threshold")


def validate_config(fields, expected_hash):
    require(isinstance(fields, dict), "invalid_scoring_config")
    require(
        set(fields) == set(STATIC_FIELDS) | set(PROFILE_FIELDS) | set(SOURCE_FIELDS),
        "scoring_config_field_set",
    )
    require(
        scoring_config_hash(fields) == expected_hash, "scoring_config_digest_mismatch"
    )
    require(
        not profile_failures({k: fields[k] for k in PROFILE_FIELDS}),
        "execution_profile_incomplete",
    )
    require(
        fields["device_type"] == "cuda" and fields["deterministic_algorithms"] is True,
        "primary_cuda_profile_required",
    )
    require(
        isinstance(fields["source_files"], list)
        and fields["source_files"]
        and fields["source_files"] == sorted(set(fields["source_files"])),
        "source_list_invalid",
    )
    require(
        isinstance(fields["source_sha256"], str)
        and DIGEST.fullmatch(fields["source_sha256"]),
        "source_digest_invalid",
    )


def create_artifact(raw_negatives, fields, bindings, created):
    direction = fields["score_direction"]
    selected = select_threshold([orient(v, direction) for v in raw_negatives])
    payload = {
        "schema_version": SCHEMA,
        "procedure": PROCEDURE,
        "alpha": 0.05,
        "alpha_numerator": 1,
        "alpha_denominator": 20,
        "scoring_config": fields,
        "scoring_config_hash": scoring_config_hash(fields),
        "score_direction": direction,
        "transform": DIRECTIONS[direction],
        "comparison": ">",
        **selected,
        **bindings,
    }
    result = envelope(payload, "artifact_sha256", created=created)
    validate_artifact(result)
    return result


def validate_artifact(value):
    require(
        isinstance(value, dict)
        and set(value) == {"payload", "artifact_sha256", "created"},
        "artifact_envelope_invalid",
    )
    p = value["payload"]
    require(isinstance(p, dict) and set(p) == ARTIFACT_KEYS, "artifact_field_set")
    require(all(finite(p[k]) for k in ("threshold_c", "alpha")), "artifact_nonfinite")
    require(
        value["artifact_sha256"] == sha(canonical_json(p)), "artifact_digest_mismatch"
    )
    require(
        p["schema_version"] == SCHEMA and p["procedure"] == PROCEDURE,
        "artifact_version",
    )
    require(
        type(p["alpha"]) is float
        and p["alpha"] == 0.05
        and type(p["alpha_numerator"]) is int
        and p["alpha_numerator"] == 1
        and type(p["alpha_denominator"]) is int
        and p["alpha_denominator"] == 20,
        "only_5pct_enabled",
    )
    require(
        type(p["n_dev_negatives"]) is int and p["n_dev_negatives"] >= 200,
        "insufficient_development_negatives",
    )
    n = p["n_dev_negatives"]
    require(
        type(p["above"]) is int and 0 <= p["above"] and 20 * p["above"] <= n,
        "invalid_exceedance_count",
    )
    require(
        type(p["ties"]) is int and 1 <= p["ties"] <= n - p["above"], "invalid_tie_count"
    )
    require(
        type(p["failed_negatives"]) is int and p["failed_negatives"] >= 0,
        "invalid_failed_negative_count",
    )
    for key in BINDINGS | {"scoring_config_hash"}:
        require(
            isinstance(p[key], str) and DIGEST.fullmatch(p[key]),
            "invalid_digest:" + key,
        )
    require(
        isinstance(p["source_run_id"], str) and p["source_run_id"], "invalid_run_id"
    )
    require(
        p["score_direction"] in DIRECTIONS
        and p["transform"] == DIRECTIONS[p["score_direction"]]
        and p["comparison"] == ">",
        "invalid_orientation_or_comparison",
    )
    validate_config(p["scoring_config"], p["scoring_config_hash"])
    require(
        p["score_direction"] == p["scoring_config"]["score_direction"],
        "direction_mismatch",
    )
    require(isinstance(value["created"], str), "invalid_created")
    try:
        datetime.datetime.fromisoformat(value["created"])
    except ValueError as error:
        raise CalibrationError("invalid_created") from error
    return p


def default_calibrations_dir():
    return pathlib.Path(__file__).resolve().parents[3] / "calibrations"


def find_calibration(config_hash, calibrations_dir=None):
    directory = pathlib.Path(calibrations_dir or default_calibrations_dir())
    if not directory.is_dir():
        return None
    matches = []
    for path in sorted(directory.glob("*.json")):
        try:
            value = strict_json(path.read_text(encoding="utf-8"))
            payload = validate_artifact(value)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
            raise CalibrationError(
                "calibration_invalid:" + path.name + ":" + str(error)
            ) from error
        if payload["scoring_config_hash"] == config_hash:
            matches.append(value)
    require(len(matches) <= 1, "ambiguous_calibration")
    return matches[0] if matches else None


def validate_score_statistics(stats):
    require(
        isinstance(stats, dict)
        and set(stats)
        == {"score", "nll_performer", "xent", "n_input_tokens", "n_target_tokens"},
        "statistics_fields",
    )
    require(
        all(finite(stats[k]) for k in ("score", "nll_performer", "xent")),
        "nonfinite_statistics",
    )
    require(
        stats["nll_performer"] >= 0 and stats["xent"] > 0 and stats["score"] >= 0,
        "invalid_statistics",
    )
    require(
        type(stats["n_input_tokens"]) is int
        and 64 <= stats["n_input_tokens"] <= 512
        and type(stats["n_target_tokens"]) is int
        and stats["n_target_tokens"] == stats["n_input_tokens"] - 1,
        "invalid_token_counts",
    )
    try:
        def f32(x):
            return struct.unpack("f", struct.pack("f", x))[0]
        require(
            f32(stats["score"]) == f32(stats["nll_performer"] / stats["xent"]),
            "score_ratio_mismatch",
        )
    except (OverflowError, struct.error) as error:
        raise CalibrationError("statistics_float32_overflow") from error


def validate_freeze(value, artifact, *, expected=None):
    require(
        isinstance(value, dict) and set(value) == {"payload", "freeze_sha256"},
        "freeze_envelope",
    )
    p = value["payload"]
    keys = {
        "schema_version",
        "calibration_file_sha256",
        "calibration_artifact_sha256",
        "scoring_config_hash",
        "scoring_config",
        "threshold_c",
        "comparison",
        "score_direction",
        "n_dev_negatives",
        "one_percent_enabled",
        "implementation_commit",
        "source_files_sha256",
        "prepared_manifest_sha256",
        "dev_set_id",
        "reconciliation_sha256",
        "scores_sha256",
        "failures_sha256",
        "dev_input_sha256",
        "lexicons",
        "quality_sources_sha256",
        "evidence_sha256",
        "historical_transfer_compliance_proven",
    }
    require(isinstance(p, dict) and set(p) == keys, "freeze_field_set")
    require(value["freeze_sha256"] == sha(canonical_json(p)), "freeze_digest_mismatch")
    a = validate_artifact(artifact)
    require(
        p["schema_version"] == "r1f-freeze-v1"
        and p["one_percent_enabled"] is False
        and p["historical_transfer_compliance_proven"] is False,
        "freeze_policy",
    )
    for key in (
        "scoring_config_hash",
        "scoring_config",
        "threshold_c",
        "comparison",
        "score_direction",
        "n_dev_negatives",
        "prepared_manifest_sha256",
        "dev_set_id",
        "reconciliation_sha256",
        "scores_sha256",
    ):
        require(p[key] == a[key], "freeze_artifact_mismatch:" + key)
    require(
        p["calibration_artifact_sha256"] == artifact["artifact_sha256"],
        "freeze_artifact_digest",
    )
    require(
        isinstance(p["implementation_commit"], str)
        and re.fullmatch(r"[0-9a-f]{40}", p["implementation_commit"]),
        "freeze_source_commit",
    )
    for key in ("calibration_file_sha256", "failures_sha256", "dev_input_sha256"):
        require(
            isinstance(p[key], str) and DIGEST.fullmatch(p[key]), "freeze_digest:" + key
        )
    for key in ("source_files_sha256", "quality_sources_sha256", "evidence_sha256"):
        require(isinstance(p[key], dict) and p[key], "freeze_map:" + key)
        require(
            all(isinstance(h, str) and DIGEST.fullmatch(h) for h in p[key].values()),
            "freeze_map_digest:" + key,
        )
    require(
        isinstance(p["lexicons"], dict)
        and set(p["lexicons"])
        == {"claim_phrases_to_inspect", "hedges", "stock_phrases"},
        "freeze_lexicons",
    )
    for name, item in p["lexicons"].items():
        require(
            isinstance(item, dict)
            and set(item) == {"version", "sha256"}
            and type(item["version"]) is int
            and item["version"] >= 1
            and isinstance(item["sha256"], str)
            and DIGEST.fullmatch(item["sha256"]),
            "freeze_lexicon:" + name,
        )
    if expected is not None:
        require(p == expected, "freeze_runtime_identity_mismatch")
    return p
