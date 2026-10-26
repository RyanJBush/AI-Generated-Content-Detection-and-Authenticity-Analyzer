"""Layer A model loading and text scoring around litmus.binoculars (SPEC §3.1).

Contract: docs/interfaces.md §2. The math lives in binoculars.py; this module only tokenizes, runs the two
models, and packages per-text results.
"""
import hashlib
from dataclasses import dataclass

import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

from litmus import config
from litmus.binoculars import NumericalScoringError, binoculars_statistics

DTYPES = {"float32": torch.float32, "bfloat16": torch.bfloat16, "float16": torch.float16}


@dataclass
class ModelPair:
    observer: object
    performer: object
    tokenizer: object
    pair: str
    observer_id: str
    performer_id: str
    device: str
    weight_dtype: str
    tokenizer_sha256: str
    attn_implementation: str


@dataclass
class ScoreResult:
    status: str  # "ok" | "too_short" | "error"
    n_tokens: int
    n_input_tokens: int
    n_scored_tokens: int | None
    truncated: bool
    nll_performer: float | None = None
    nll_observer: float | None = None
    xent: float | None = None
    score: float | None = None
    error: str | None = None


def resolve_device(device):
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if device not in ("cuda", "cpu"):
        raise ValueError(f"device must be auto, cuda or cpu, got {device!r}")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("device=cuda requested but CUDA is unavailable")
    return device


def _tokenizer_json_sha256(name, revision):
    with open(hf_hub_download(name, "tokenizer.json", revision=revision), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_pair(pair=config.DEFAULT_PAIR, device="auto", dtype="float32"):
    """Load the pinned observer/performer pair with explicit weight dtype and device."""
    observer_name, performer_name = config.PAIRS[pair]
    observer_rev = config.MODEL_REVISIONS[observer_name]
    performer_rev = config.MODEL_REVISIONS[performer_name]
    if dtype not in DTYPES:
        raise ValueError(f"dtype must be one of {sorted(DTYPES)}, got {dtype!r}")
    device = resolve_device(device)

    tokenizer_sha256 = _tokenizer_json_sha256(observer_name, observer_rev)
    if _tokenizer_json_sha256(performer_name, performer_rev) != tokenizer_sha256:
        raise ValueError(f"tokenizer.json differs between {observer_name} and {performer_name}")
    tokenizer = AutoTokenizer.from_pretrained(observer_name, revision=observer_rev)
    tokenizer.padding_side = config.PADDING_SIDE
    tokenizer.truncation_side = config.TRUNCATION_SIDE
    if tokenizer.pad_token is None:
        raise ValueError(f"{observer_name} tokenizer has no pad token")

    models = []
    for name, revision in ((observer_name, observer_rev), (performer_name, performer_rev)):
        model = AutoModelForCausalLM.from_pretrained(name, revision=revision, dtype=DTYPES[dtype])
        models.append(model.to(device).eval())
    observer, performer = models
    obs_dim = observer.get_output_embeddings().weight.shape[0]
    perf_dim = performer.get_output_embeddings().weight.shape[0]
    if obs_dim != perf_dim:
        raise ValueError(f"output dimensions differ: observer {obs_dim}, performer {perf_dim}")

    return ModelPair(
        observer=observer,
        performer=performer,
        tokenizer=tokenizer,
        pair=pair,
        observer_id=f"{observer_name}@{observer_rev}",
        performer_id=f"{performer_name}@{performer_rev}",
        device=device,
        weight_dtype=dtype,
        tokenizer_sha256=tokenizer_sha256,
        attn_implementation=observer.config._attn_implementation,
    )


def _encode(tokenizer, text):
    ids = tokenizer(
        text, add_special_tokens=config.ADD_SPECIAL_TOKENS, split_special_tokens=config.SPLIT_SPECIAL_TOKENS
    )["input_ids"]
    return ids, ids[: config.MAX_LENGTH]  # right truncation keeps the first MAX_LENGTH tokens


def score_texts(texts, pair, batch_size=1):
    """Score raw texts (unmodified) with the pair; returns one ScoreResult per text, in order."""
    results = [None] * len(texts)
    pending = []
    for i, text in enumerate(texts):
        full, kept = _encode(pair.tokenizer, text)
        if len(full) < config.MIN_INPUT_TOKENS:
            results[i] = ScoreResult(status="too_short", n_tokens=len(full), n_input_tokens=len(kept),
                                     n_scored_tokens=None, truncated=len(full) > len(kept))
        else:
            pending.append((i, len(full), kept))

    pad_id = pair.tokenizer.pad_token_id
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        width = max(len(kept) for _, _, kept in batch)
        input_ids = torch.full((len(batch), width), pad_id, dtype=torch.long)
        attention_mask = torch.zeros((len(batch), width), dtype=torch.long)
        for row, (_, _, kept) in enumerate(batch):
            input_ids[row, : len(kept)] = torch.tensor(kept, dtype=torch.long)
            attention_mask[row, : len(kept)] = 1
        input_ids = input_ids.to(pair.device)
        attention_mask = attention_mask.to(pair.device)

        with torch.inference_mode():
            obs_logits = pair.observer(input_ids=input_ids, attention_mask=attention_mask, use_cache=False).logits
            perf_logits = pair.performer(input_ids=input_ids, attention_mask=attention_mask, use_cache=False).logits
            for row, (i, n_tokens, kept) in enumerate(batch):
                # Per-document call so one document's numerical failure does not discard the others.
                length = len(kept)
                common = {"status": "ok", "n_tokens": n_tokens, "n_input_tokens": length,
                          "n_scored_tokens": length - 1, "truncated": n_tokens > length}
                try:
                    stats = binoculars_statistics(
                        obs_logits[row:row + 1, :length], perf_logits[row:row + 1, :length],
                        input_ids[row:row + 1, :length], attention_mask[row:row + 1, :length],
                    )
                except NumericalScoringError as e:
                    results[i] = ScoreResult(**{**common, "status": "error"}, error=str(e))
                    continue
                results[i] = ScoreResult(
                    **common,
                    nll_performer=float(stats["nll_performer"][0]),
                    nll_observer=float(stats["nll_observer"][0]),
                    xent=float(stats["xent"][0]),
                    score=float(stats["score"][0]),
                )
    return results


def score_text(text, pair):
    return score_texts([text], pair)[0]
