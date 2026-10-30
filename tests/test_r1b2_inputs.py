"""R1-B2 synthetic input generator: exact token counts and determinism.

The exact-count tests use the real observer tokenizer under the production
preprocessing (models/ must be installed; missing files fail, not skip). The
generator logic itself is also tested with a stand-in counter, model-free.
"""
import hashlib
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
INPUTS = ROOT / "eval" / "inputs" / "r1b2"
_spec = importlib.util.spec_from_file_location(
    "r1b2_inputs", ROOT / "scripts" / "r1b2_inputs.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

MANIFEST = json.loads((INPUTS / "manifest.json").read_text(encoding="utf-8"))


def word_count(_tokenizer, text):
    # Stand-in counter: one token per word plus one per period
    return len(text.split()) + text.count(".")


@pytest.mark.parametrize("n", [1, 7, 64, 512])
def test_generator_hits_exact_count_with_stand_in_counter(n):
    text = gen.generate(None, n, seed=5, count=word_count)
    assert word_count(None, text) == n


def test_generator_is_deterministic_and_seed_dependent():
    a = gen.generate(None, 128, seed=11, count=word_count)
    assert a == gen.generate(None, 128, seed=11, count=word_count)
    assert a != gen.generate(None, 128, seed=12, count=word_count)


def test_manifest_lists_10_texts_per_length_with_matching_sha256():
    files = MANIFEST["files"]
    assert sorted({e["target_tokens"] for e in files}) == list(gen.LENGTHS)
    for n in gen.LENGTHS:
        assert sum(e["target_tokens"] == n for e in files) == gen.TEXTS_PER_LENGTH
    assert len({e["sha256"] for e in files}) == len(files)  # distinct texts
    for e in files:
        data = (INPUTS / e["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == e["sha256"], e["file"]
        assert e["seed"] == gen.seed_for(e["target_tokens"],
                                         int(e["file"][7:9]))
        data.decode("ascii")  # plain ASCII, no dataset text


@pytest.fixture(scope="module")
def tokenizer():
    mp = pytest.MonkeyPatch()
    # load_tokenizer sets the HF offline variables; restore them afterwards
    mp.setenv("HF_HUB_OFFLINE", "1")
    mp.setenv("TRANSFORMERS_OFFLINE", "1")
    try:
        yield gen.load_tokenizer()
    finally:
        mp.undo()


def test_committed_inputs_have_exact_production_token_counts(tokenizer):
    from litmus.scorer.tokenize import tokenize_window

    for e in MANIFEST["files"]:
        text = (INPUTS / e["file"]).read_bytes().decode("utf-8")
        window = tokenize_window(tokenizer, text)
        assert window.tokens_total == e["target_tokens"] == e["tokens_verified"]
        assert not window.truncated


@pytest.mark.parametrize("n", gen.LENGTHS)
def test_regeneration_reproduces_committed_bytes(tokenizer, n):
    # One text per length, regenerated with the real tokenizer
    text = gen.generate(tokenizer, n, gen.seed_for(n, 0))
    assert text.encode("ascii") == (INPUTS / gen.file_name(n, 0)).read_bytes()
