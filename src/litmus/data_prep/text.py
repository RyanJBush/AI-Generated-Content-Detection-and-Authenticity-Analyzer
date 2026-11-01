"""Tokenizer-only row eligibility; preserves exact decoded text."""

import hashlib
import importlib.metadata
import os
import sys

from litmus import config
from litmus.data_prep.acquisition import PrepError, file_hash
from litmus.data_prep.keys import canonical
from litmus.scorer.tokenize import tokenize_window


def assess(text, tokenizer):
    errors = []
    if not isinstance(text, str):
        return {}, ["not_text"]
    if "\0" in text:
        errors.append("nul")
    controls = sum(ord(c) < 32 and c not in "\t\n\r\f" for c in text)
    if text and controls / len(text) >= 0.01:
        errors.append("control_share")
    if len(text) > 200000:
        errors.append("text_too_long")
    if not text.strip():
        errors.append("whitespace_only")
    encoded = text.encode("utf-8", errors="strict")
    if len(encoded) > 50000000:
        errors.append("text_bytes_too_long")
    result = {
        "raw_text_sha256": hashlib.sha256(encoded).hexdigest(),
        "codepoints": len(text),
        "utf8_bytes": len(encoded),
    }
    if errors:
        return result, errors
    window = tokenize_window(tokenizer, text)
    result.update(window.scored_window())
    result["scored_window_sha256"] = hashlib.sha256(canonical(window.ids)).hexdigest()
    if window.tokens_scored < config.MIN_TOKENS:
        errors.append("too_short")
    return result, errors


def load_local_tokenizer(repo):
    if "torch" in sys.modules:
        raise PrepError("torch_already_imported; use a fresh tokenizer-only process")
    os.environ["USE_TORCH"] = "0"
    os.environ["USE_TF"] = "0"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    directory = repo / "models" / config.OBSERVER_DIR
    if file_hash(directory / "tokenizer.json") != config.TOKENIZER_JSON_SHA256:
        raise PrepError("tokenizer_identity_mismatch")
    assets = {
        p.name: file_hash(p)
        for p in directory.iterdir()
        if p.name
        in (
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.json",
            "merges.txt",
            "added_tokens.json",
            "config.json",
        )
    }
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
    if "torch" in sys.modules:
        raise PrepError("tokenizer_imported_model_runtime")
    identity = {
        "observer_revision": config.OBSERVER_COMMIT,
        "assets": assets,
        "add_special_tokens": config.ADD_SPECIAL_TOKENS,
        "split_special_tokens": config.SPLIT_SPECIAL_TOKENS,
        "truncation_side": config.TRUNCATION_SIDE,
        "max_tokens": config.MAX_TOKENS,
        "min_tokens": config.MIN_TOKENS,
        "preprocessing_version": config.PREPROCESSING_VERSION,
        "libraries": {
            n: importlib.metadata.version(n)
            for n in ("transformers", "tokenizers", "huggingface_hub")
        },
    }
    return tokenizer, identity
