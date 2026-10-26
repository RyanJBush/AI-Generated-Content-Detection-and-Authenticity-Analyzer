"""Scoring identity, execution profile, and their hashes (SPEC §3.1; contract: docs/interfaces.md §3)."""
import hashlib
import json
import platform
import sys
from pathlib import Path

import tokenizers
import torch
import transformers

from litmus import config

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
SCORER_SOURCE_FILES = ["binoculars.py", "scoring.py", "config.py", "identity.py"]

POSITIONAL_RULE = ("numerator: logits at t score x_{t+1}, m_t = a_t * a_{t+1}; "
                   "denominator: all real input positions t incl. final")
MASKING_RULE = "attention_mask only; right padding; no pad_token_id comparison"


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _normalized_file_sha256(path):
    """SHA-256 of a text file with CRLF converted to LF, so Windows and Linux checkouts agree."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"required identity file missing: {path}")
    return sha256_hex(path.read_bytes().replace(b"\r\n", b"\n"))


def compute_identity(pair):
    scoring_identity = {
        "observer": pair.observer_id,
        "performer": pair.performer_id,
        "tokenizer_sha256": pair.tokenizer_sha256,
        "tokenizer_settings": {
            "add_special_tokens": config.ADD_SPECIAL_TOKENS,
            "split_special_tokens": config.SPLIT_SPECIAL_TOKENS,
            "padding_side": config.PADDING_SIDE,
            "truncation_side": config.TRUNCATION_SIDE,
            "max_length": config.MAX_LENGTH,
            "chat_template": None,
        },
        "min_input_tokens": config.MIN_INPUT_TOKENS,
        "positional_rule": POSITIONAL_RULE,
        "masking_rule": MASKING_RULE,
        "reduction_dtype": config.REDUCTION_DTYPE,
        "scorer_version": config.SCORER_VERSION,
        "preprocessing_version": config.PREPROCESSING_VERSION,
        "source_sha256": {
            f"src/litmus/{name}": _normalized_file_sha256(PACKAGE_DIR / name) for name in SCORER_SOURCE_FILES
        },
    }
    execution_profile = {
        "weight_dtype": pair.weight_dtype,
        "device": pair.device,
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "transformers": transformers.__version__,
        "tokenizers": tokenizers.__version__,
        "attn_implementation": pair.attn_implementation,
        "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "requirements_lock_sha256": _normalized_file_sha256(REPO_ROOT / "requirements.lock"),
    }
    identity_hash = sha256_hex(canonical_json(scoring_identity))
    profile_hash = sha256_hex(canonical_json(execution_profile))
    return {
        "scoring_identity": scoring_identity,
        "scoring_identity_hash": identity_hash,
        "execution_profile": execution_profile,
        "execution_profile_hash": profile_hash,
        "scoring_config_hash": sha256_hex(canonical_json(
            {"scoring_identity_hash": identity_hash, "execution_profile_hash": profile_hash}
        )),
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "gpu": torch.cuda.get_device_name(0) if pair.device == "cuda" else None,
            "cuda_driver_version": torch._C._cuda_getDriverVersion() if pair.device == "cuda" else None,
            "cpu_threads": torch.get_num_threads(),
        },
    }
