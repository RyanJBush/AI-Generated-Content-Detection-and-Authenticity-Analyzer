"""Model-free stand-ins for the tokenizer and causal LMs (no downloads)."""
from types import SimpleNamespace

import torch

from litmus.scoring import ModelPair

VOCAB = 7


class FakeTokenizer:
    """Whitespace tokenizer: word -> (len(word) mod VOCAB-1) + 1; ID 0 is the pad token."""

    pad_token_id = 0

    def __init__(self):
        self.calls = []

    def __call__(self, text, **kwargs):
        self.calls.append(kwargs)
        return {"input_ids": [len(w) % (VOCAB - 1) + 1 for w in text.split()]}


class FakeLM:
    """Logits depend only on the token at each position, so right padding cannot change real positions."""

    def __init__(self, seed, nan_token=None):
        generator = torch.Generator().manual_seed(seed)
        self.table = torch.randn(VOCAB, VOCAB, generator=generator)
        self.nan_token = nan_token
        self.inputs = []

    def __call__(self, input_ids, attention_mask, use_cache):
        assert use_cache is False
        self.inputs.append((input_ids.clone(), attention_mask.clone()))
        logits = self.table[input_ids].clone()
        if self.nan_token is not None:
            logits[input_ids == self.nan_token] = float("nan")
        return SimpleNamespace(logits=logits)


def fake_pair(nan_token=None):
    return ModelPair(
        observer=FakeLM(seed=1, nan_token=nan_token),
        performer=FakeLM(seed=2, nan_token=nan_token),
        tokenizer=FakeTokenizer(),
        pair="fake",
        observer_id="fake/observer@0",
        performer_id="fake/performer@0",
        device="cpu",
        weight_dtype="float32",
        tokenizer_sha256="0" * 64,
        attn_implementation="fake",
    )


def words(n, word="ab"):
    return " ".join([word] * n)
