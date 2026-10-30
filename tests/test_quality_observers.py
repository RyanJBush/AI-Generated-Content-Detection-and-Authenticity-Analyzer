"""R1-C2: text quality observers (model-free)."""
import pathlib
import subprocess
import sys

import pytest

from litmus.quality import observers as obs_mod
from litmus.quality.lexicon import LexiconError, load_lexicon
from litmus.quality.observers import (
    CLAIM_LABEL,
    OBSERVER_IDS,
    SPAN_CAP,
    RepeatedWord3Grams,
    build_observers,
    observe_all,
)
from litmus.quality.words import word_index
from litmus.schemas import QualityStatus

FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "inputs" / "quality.txt")
SAMPLE = FIXTURE.read_bytes().decode("utf-8")


@pytest.fixture(scope="module")
def observers():
    return build_observers()


def run(text, observers):
    records = observe_all(text, observers)
    assert [r.observer_id for r in records] == list(OBSERVER_IDS)
    for r in records:
        for start, end in r.spans:
            assert 0 <= start < end <= len(text)
        assert r.spans == sorted(r.spans)
    return {r.observer_id: r for r in records}


def surface(text, record):
    return [text[s:e] for s, e in record.spans]


# --- unit: exact counts and spans ---

def test_fixture_exact_counts_spans_and_rates(observers):
    r = run(SAMPLE, observers)
    assert word_index(SAMPLE).count == 33
    assert surface(SAMPLE, r["stock_phrases"]) == ["It is important to note",
                                                   "In conclusion"]
    assert r["stock_phrases"].spans == [[0, 23], [134, 147]]
    assert surface(SAMPLE, r["hedges"]) == ["Perhaps", "it seems", "likely"]
    assert r["hedges"].spans == [[57, 64], [149, 157], [158, 164]]
    assert surface(SAMPLE, r["claim_phrases_to_inspect"]) == ["studies show",
                                                              "data shows"]
    assert r["claim_phrases_to_inspect"].spans == [[29, 41], [69, 79]]
    assert surface(SAMPLE, r["repeated_word_3grams"]) == [
        "The cat sat", "cat sat on", "sat on the", "on the mat"] * 2
    for oid, count in [("stock_phrases", 2), ("hedges", 3),
                       ("repeated_word_3grams", 8), ("claim_phrases_to_inspect", 2)]:
        assert r[oid].count == count
        assert r[oid].status == QualityStatus.OBSERVED
        assert r[oid].rate_per_100_words == count / 33 * 100


def test_notes_fixed_format(observers):
    r = run(SAMPLE, observers)
    hedges = load_lexicon("hedges")
    assert r["hedges"].notes == [
        "observer_version=1", "lexicon_name=hedges", "lexicon_version=1",
        f"lexicon_sha256={hedges.sha256}", "spans_truncated=false",
        "spans_reported=3"]
    assert r["repeated_word_3grams"].notes == [
        "observer_version=1", "spans_truncated=false", "spans_reported=8"]
    claim = r["claim_phrases_to_inspect"].notes
    assert claim[-1] == CLAIM_LABEL == (
        "label=phrase to inspect; not evidence that a claim is unsupported")
    assert all(r[o].observer_version == "1" for o in OBSERVER_IDS)


def test_none_found_with_words_has_zero_rate(observers):
    r = run("Plain words here and nothing else.", observers)
    for oid in OBSERVER_IDS:
        assert r[oid].status == QualityStatus.NONE_FOUND
        assert r[oid].count == 0 and r[oid].spans == []
        assert r[oid].rate_per_100_words == 0.0


@pytest.mark.parametrize("text", ["", "   \n\t ", "... !!! --"])
def test_zero_words_gives_null_rate(observers, text):
    r = run(text, observers)
    for oid in OBSERVER_IDS:
        assert r[oid].status == QualityStatus.NONE_FOUND
        assert r[oid].count == 0 and r[oid].spans == []
        assert r[oid].rate_per_100_words is None


def test_3grams_cross_punctuation_and_line_breaks_and_fold_case():
    text = "the cat sat.\nThe CAT, sat"
    rec = RepeatedWord3Grams().observe(text, word_index(text))
    assert surface(text, rec) == ["the cat sat", "The CAT, sat"]


def test_3grams_overlapping_occurrences():
    text = "x x x x"
    rec = RepeatedWord3Grams().observe(text, word_index(text))
    assert rec.count == 2 and rec.spans == [[0, 5], [2, 7]]


def test_no_stop_word_filtering():
    text = "one of the best and one of the rest"
    rec = RepeatedWord3Grams().observe(text, word_index(text))
    assert surface(text, rec) == ["one of the", "one of the"]


# --- metamorphic ---

BASE = "Alpha bravo charlie delta echo foxtrot golf hotel."


@pytest.mark.parametrize("oid, phrase", [
    ("stock_phrases", "delve into"),
    ("hedges", "arguably"),
    ("claim_phrases_to_inspect", "experts agree"),
])
def test_inserting_one_phrase_adds_exactly_one(observers, oid, phrase):
    before = run(BASE, observers)
    text = BASE.replace("delta echo", f"delta {phrase} echo")
    after = run(text, observers)
    assert after[oid].count == before[oid].count + 1
    assert word_index(text).count == word_index(BASE).count + len(phrase.split())
    for other in OBSERVER_IDS:
        if other not in (oid, "repeated_word_3grams"):
            assert after[other].count == before[other].count


def test_duplicating_a_sentence_adds_2_times_w_minus_2(observers):
    sentence = "Alpha bravo charlie delta echo foxtrot."  # w = 6 distinct words
    assert run(sentence, observers)["repeated_word_3grams"].count == 0
    doubled = sentence + " " + sentence
    # The 4 internal 3-grams each occur twice; boundary 3-grams are unique
    assert run(doubled, observers)["repeated_word_3grams"].count == 2 * (6 - 2)


@pytest.mark.parametrize("text, expected", [
    ("Recent studies show growth.", 1),
    ("Recent studies show 42% growth.", 1),  # number after whitespace: unchanged
    ("Recent studies show, 42 cases.", 1),
    ("Recent studies show42 growth.", 0),  # digits are word characters
])
def test_number_after_studies_show(observers, text, expected):
    assert run(text, observers)["claim_phrases_to_inspect"].count == expected


# --- span integrity ---

INTEGRITY = ("\U0001F600 caf\u00e9 \u4e2d\u6587 perhaps; stra\u00dfe STRA\u1e9eE "
             "studies show it\u200bseems p\u0435rhaps cafe\u0301 delve into "
             "\U0001F469\u200d\U0001F4BB the cat sat \u0441at the cat sat")


def test_span_integrity_with_unicode(observers):
    r = run(INTEGRITY, observers)
    assert surface(INTEGRITY, r["hedges"]) == ["perhaps"]  # homoglyph and ZWSP miss
    assert surface(INTEGRITY, r["stock_phrases"]) == ["delve into"]
    assert surface(INTEGRITY, r["claim_phrases_to_inspect"]) == ["studies show"]
    assert surface(INTEGRITY, r["repeated_word_3grams"]) == ["the cat sat",
                                                             "the cat sat"]
    start = INTEGRITY.index("perhaps")
    assert r["hedges"].spans == [[start, start + 7]]


# --- span cap ---

def test_span_cap_keeps_exact_count(observers):
    text = "perhaps " * 1500
    r = run(text, observers)
    hedges = r["hedges"]
    assert hedges.count == 1500 and len(hedges.spans) == SPAN_CAP == 1000
    assert "spans_truncated=true" in hedges.notes
    assert "spans_reported=1000" in hedges.notes
    assert hedges.spans[-1] == [999 * 8, 999 * 8 + 7]
    grams = r["repeated_word_3grams"]
    assert grams.count == 1498 and len(grams.spans) == 1000
    assert "spans_truncated=true" in grams.notes


def test_exactly_cap_is_not_truncated(observers):
    r = run("perhaps " * 1000, observers)
    assert r["hedges"].count == 1000
    assert "spans_truncated=false" in r["hedges"].notes
    assert "spans_reported=1000" in r["hedges"].notes


# --- large input (no wall-clock assertion) ---

def test_200k_code_points_complete_with_exact_results(observers):
    text = "perhaps " * 25000
    assert len(text) == 200_000
    r = run(text, observers)
    assert r["hedges"].count == 25000
    assert r["repeated_word_3grams"].count == 24998
    assert r["stock_phrases"].count == 0
    assert len(r["hedges"].spans) == 1000


def test_200k_prose_completes(observers):
    unit = SAMPLE.replace("\n", " ")
    text = (unit * (200_000 // len(unit) + 1))[:200_000]
    r = run(text, observers)
    assert all(r[o].status in (QualityStatus.OBSERVED, QualityStatus.NONE_FOUND)
               for o in OBSERVER_IDS)
    assert r["stock_phrases"].count >= 2 * (200_000 // len(unit))


def test_one_200k_word_and_200k_cjk():
    for text in ("a" * 200_000, "\u4e2d" * 200_000):
        r = observe_all(text, build_observers())
        assert word_index(text).count == 1
        assert all(x.count == 0 for x in r)


# --- error isolation ---

def test_raising_observer_is_isolated(observers, monkeypatch):
    baseline = run(SAMPLE, observers)

    def boom(self, text, words):
        raise RuntimeError("injected")

    monkeypatch.setattr(RepeatedWord3Grams, "observe", boom)
    r = run(SAMPLE, observers)
    err = r["repeated_word_3grams"]
    assert err.status == QualityStatus.ERROR
    assert err.count is None and err.rate_per_100_words is None and err.spans == []
    assert err.notes == ["observer_version=1", "error=RuntimeError"]
    for oid in ("stock_phrases", "hedges", "claim_phrases_to_inspect"):
        assert r[oid] == baseline[oid]


def test_invalid_lexicon_gives_error_record(monkeypatch):
    def bad(name):
        raise LexiconError("no valid entries")

    monkeypatch.setattr(obs_mod, "load_lexicon", bad)
    r = {x.observer_id: x for x in observe_all(SAMPLE, build_observers())}
    for oid in ("stock_phrases", "hedges", "claim_phrases_to_inspect"):
        assert r[oid].status == QualityStatus.ERROR
        assert r[oid].notes == ["observer_version=1",
                                "lexicon_invalid=no valid entries"]
    assert r["repeated_word_3grams"].count == 8


# --- import isolation (constructing and running all four observers) ---

ISOLATION = r"""
import sys
import litmus
from litmus.quality.observers import build_observers, observe_all
records = observe_all("It is important to note that studies show it. "
                      "the cat sat the cat sat", build_observers())
assert [r.count for r in records] == [1, 0, 2, 1], [r.count for r in records]
bad = sorted(m for m in sys.modules
             if m.split(".")[0] in ("torch", "transformers")
             or m == "litmus.scorer" or m.startswith("litmus.scorer."))
print(bad)
sys.exit(1 if bad else 0)
"""


def test_observers_do_not_import_the_model_stack():
    proc = subprocess.run([sys.executable, "-I", "-c", ISOLATION],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert proc.stdout.strip() == "[]"
