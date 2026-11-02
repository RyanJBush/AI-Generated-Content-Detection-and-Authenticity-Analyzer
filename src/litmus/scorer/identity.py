"""scoring_config_hash and source identity (R1-PLAN §1.2, strict matching).

See docs/interfaces.md for the field list and the source file list.
"""

import hashlib
import json
import pathlib
from typing import Any, Dict, Iterable, List, Tuple

from litmus import config

# Fixed source file list (repository-relative); the list itself is hashed
SOURCE_FILES: Tuple[str, ...] = (
    "src/litmus/calibration_run.py",
    "src/litmus/config.py",
    "src/litmus/ingestion.py",
    "src/litmus/scorer/analyzer.py",
    "src/litmus/scorer/binoculars.py",
    "src/litmus/scorer/calibration.py",
    "src/litmus/scorer/identity.py",
    "src/litmus/scorer/loader.py",
    "src/litmus/scorer/tokenize.py",
)
_SRC_ROOT = pathlib.Path(__file__).resolve().parents[3]

# A4 fields and the preprocessing policy (static, from litmus.config)
STATIC_FIELDS = (
    "scorer_version",
    "formula_id",
    "observer_repo",
    "observer_commit",
    "performer_repo",
    "performer_commit",
    "tokenizer_json_sha256",
    "add_special_tokens",
    "split_special_tokens",
    "truncation_side",
    "max_tokens",
    "min_tokens",
    "weight_dtype",
    "reduction_dtype",
    "score_direction",
    "preprocessing_version",
)
# Numerical execution profile (read back at runtime; see loader.read_profile)
PROFILE_FIELDS = (
    "device_type",
    "gpu_name",
    "nvidia_driver_version",
    "cuda_runtime",
    "torch_version",
    "transformers_version",
    "tokenizers_version",
    "attn_implementation",
    "batch_size",
    "matmul_allow_tf32",
    "cudnn_allow_tf32",
    "float32_matmul_precision",
    "deterministic_algorithms",
    "cublas_workspace_config",
    "weight_dtype",
    "reduction_dtype",
    "os_family",
    "cuda_initialized_before_settings",
)
SOURCE_FIELDS = ("source_files", "source_sha256")


def static_fields(
    tokenizer_json_sha256: str = config.TOKENIZER_JSON_SHA256,
) -> Dict[str, Any]:
    return {
        "scorer_version": config.SCORER_VERSION,
        "formula_id": config.FORMULA_ID,
        "observer_repo": config.OBSERVER_REPO,
        "observer_commit": config.OBSERVER_COMMIT,
        "performer_repo": config.PERFORMER_REPO,
        "performer_commit": config.PERFORMER_COMMIT,
        "tokenizer_json_sha256": tokenizer_json_sha256,
        "add_special_tokens": config.ADD_SPECIAL_TOKENS,
        "split_special_tokens": config.SPLIT_SPECIAL_TOKENS,
        "truncation_side": config.TRUNCATION_SIDE,
        "max_tokens": config.MAX_TOKENS,
        "min_tokens": config.MIN_TOKENS,
        "weight_dtype": config.WEIGHT_DTYPE,
        "reduction_dtype": config.REDUCTION_DTYPE,
        "score_direction": config.SCORE_DIRECTION,
        "preprocessing_version": config.PREPROCESSING_VERSION,
    }


def normalized_file_sha256(data: bytes) -> str:
    """SHA-256 of file bytes after CRLF -> LF (source files only)."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def source_sha256(
    files: Iterable[str] = SOURCE_FILES, root: pathlib.Path = _SRC_ROOT
) -> str:
    """SHA-256 over sorted "path\\nsha256" entries joined by "\\n"."""
    entries = []
    for rel in sorted(files):
        data = (root / rel).read_bytes()
        entries.append(f"{rel}\n{normalized_file_sha256(data)}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def canonical_json(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def config_fields(
    profile: Dict[str, Any],
    static: Dict[str, Any],
    source_files: List[str],
    source_hash: str,
) -> Dict[str, Any]:
    """The flat dict that is hashed. Profile values for weight/reduction dtype
    are the read-back values and must agree with the static ones."""
    missing = [f for f in PROFILE_FIELDS if f not in profile]
    if missing:
        raise KeyError(f"profile is missing fields: {missing}")
    fields = dict(static)
    for name in PROFILE_FIELDS:
        if name in fields and fields[name] != profile[name]:
            raise ValueError(
                f"profile {name}={profile[name]!r} disagrees with "
                f"configuration {fields[name]!r}"
            )
        fields[name] = profile[name]
    fields["source_files"] = list(source_files)
    fields["source_sha256"] = source_hash
    return fields


def scoring_config_hash(fields: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(fields)).hexdigest()
