"""Model-free tests for litmus.scoring (tokenization policy, too_short, truncation, batching, errors)."""
import math

import torch
from fakes import fake_pair, words

from litmus import config
from litmus.binoculars import binoculars_statistics
from litmus.scoring import score_text, score_texts


def test_too_short_skips_models_and_returns_null_statistics():
    pair = fake_pair()
    result = score_text(words(config.MIN_INPUT_TOKENS - 1), pair)
    assert result.status == "too_short"
    assert result.n_tokens == 63
    assert result.n_scored_tokens is None
    assert (result.nll_performer, result.nll_observer, result.xent, result.score) == (None, None, None, None)
    assert pair.observer.inputs == [] and pair.performer.inputs == []


def test_minimum_length_is_scored():
    result = score_text(words(config.MIN_INPUT_TOKENS), fake_pair())
    assert result.status == "ok"
    assert (result.n_tokens, result.n_input_tokens, result.n_scored_tokens) == (64, 64, 63)
    assert not result.truncated
    assert all(math.isfinite(v) for v in (result.nll_performer, result.nll_observer, result.xent, result.score))


def test_tokenizer_policy_is_explicit():
    pair = fake_pair()
    score_text(words(70), pair)
    assert pair.tokenizer.calls == [{"add_special_tokens": False, "split_special_tokens": False}]


def test_right_truncation_keeps_first_512_tokens():
    pair = fake_pair()
    text = " ".join(["a"] * 300 + ["abc"] * 300)  # IDs 2 then 4
    result = score_text(text, pair)
    assert (result.n_tokens, result.n_input_tokens, result.n_scored_tokens) == (600, 512, 511)
    assert result.truncated
    seen_ids, seen_mask = pair.observer.inputs[0]
    assert seen_ids.shape == (1, 512)
    assert seen_ids[0, :300].eq(2).all() and seen_ids[0, 300:].eq(4).all()
    assert seen_mask.eq(1).all()


def test_values_come_from_binoculars_statistics_with_observer_performer_roles():
    pair = fake_pair()
    text = " ".join(["a", "abc", "abcdef", "ab"] * 20)
    result = score_text(text, pair)
    ids = torch.tensor([pair.tokenizer(text)["input_ids"]])
    mask = torch.ones_like(ids)
    expected = binoculars_statistics(pair.observer.table[ids], pair.performer.table[ids], ids, mask)
    for key in ["nll_performer", "nll_observer", "xent", "score"]:
        assert getattr(result, key) == float(expected[key][0])


def test_batched_right_padding_matches_single_scoring():
    texts = [words(64, "a"), " ".join(["ab", "abcd"] * 50), words(10), " ".join(["abc", "a", "abcde"] * 40)]
    single = score_texts(texts, fake_pair(), batch_size=1)
    pair = fake_pair()
    batched = score_texts(texts, pair, batch_size=3)
    assert single == batched
    assert [r.status for r in batched] == ["ok", "ok", "too_short", "ok"]
    # The too_short text is never sent; the 3 scorable texts form one right-padded batch.
    assert [inp[0].shape for inp in pair.observer.inputs] == [torch.Size([3, 120])]
    assert pair.observer.inputs[0][1].sum(dim=1).tolist() == [64, 100, 120]


def test_numerical_error_is_isolated_to_its_document():
    # Token ID 6 (5-letter words) produces NaN logits; the other document in the batch still scores.
    texts = [words(70, "ab"), " ".join(["ab"] * 69 + ["abcde"])]
    results = score_texts(texts, fake_pair(nan_token=6), batch_size=2)
    assert results[0].status == "ok" and math.isfinite(results[0].score)
    assert results[1].status == "error"
    assert "not finite" in results[1].error
    assert results[1].score is None and results[1].n_input_tokens == 70
