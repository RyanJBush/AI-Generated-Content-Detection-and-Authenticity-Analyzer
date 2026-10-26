"""Layer B tests (SPEC §8.2): unit, metamorphic, span integrity, robustness. No models."""
import re

import pytest

from litmus.slop import FEATURES, WORD_RE, analyze, find_lexicon_matches, load_lexicons


@pytest.fixture(scope="module")
def lexicons():
    return load_lexicons()


def spans(result, feature):
    return result["features"][feature]["spans"]


def matches(result, feature):
    return result["features"][feature]["matches"]


def counts(result):
    return {f: result["features"][f]["count"] for f in FEATURES}


# --- Lexicon files -------------------------------------------------------------------------------------------


def test_lexicons_load_without_comments(lexicons):
    assert set(lexicons) == {"stock_phrases", "hedges", "inspect_phrases"}
    for entries in lexicons.values():
        assert entries and not any(e.startswith("#") or not e.strip() for e in entries)
        assert len({e.lower() for e in entries}) == len(entries)
    assert "studies show" in lexicons["inspect_phrases"]


# --- Unit tests: exact counts and spans ----------------------------------------------------------------------


def test_stock_phrases(lexicons):
    text = "We delve into data. In conclusion, it is worth noting the rich tapestry."
    result = analyze(text, lexicons)
    assert spans(result, "stock_phrases") == [[3, 13], [20, 33], [35, 53], [58, 71]]
    assert matches(result, "stock_phrases") == ["delve into", "in conclusion", "it is worth noting", "rich tapestry"]
    assert result["n_words"] == 13
    assert result["features"]["stock_phrases"]["rate"] == pytest.approx(100 * 4 / 13)


def test_lexicon_matching_is_case_insensitive_at_word_boundaries(lexicons):
    entries = lexicons["stock_phrases"]
    assert [m[:2] for m in find_lexicon_matches("DELVE INTO it", entries)] == [(0, 10)]
    assert find_lexicon_matches("delve intolerance", entries) == []
    assert find_lexicon_matches("redelve into", entries) == []
    assert find_lexicon_matches("delve_into", entries) == []


def test_lexicon_whitespace_and_apostrophes(lexicons):
    entries = lexicons["stock_phrases"]
    assert [m[2] for m in find_lexicon_matches("Delve\n  into it", entries)] == ["delve into"]
    assert [m[2] for m in find_lexicon_matches("It’s worth noting", entries)] == ["it's worth noting"]
    assert [m[2] for m in find_lexicon_matches("It's worth noting", entries)] == ["it's worth noting"]


def test_overlapping_entries_resolve_leftmost_longest():
    entries = ["studies show", "recent studies show", "show that"]
    found = find_lexicon_matches("recent studies show that", entries)
    assert found == [(0, 19, "recent studies show")]
    # Leftmost wins over longer-but-later; the later overlapping candidate is dropped.
    assert find_lexicon_matches("studies show that", ["show that", "studies show"]) == [(0, 12, "studies show")]


def test_hedges(lexicons):
    text = "Perhaps it might work; arguably it tends to fail."
    result = analyze(text, lexicons)
    assert matches(result, "hedges") == ["perhaps", "might", "arguably", "tends to"]
    assert spans(result, "hedges") == [[0, 7], [11, 16], [23, 31], [35, 43]]


def test_inspect_phrases(lexicons):
    text = "Studies show that experts agree."
    result = analyze(text, lexicons)
    assert matches(result, "inspect_phrases") == ["studies show", "experts agree"]
    assert spans(result, "inspect_phrases") == [[0, 12], [18, 31]]


def test_repeated_ngrams():
    result = analyze("the cat sat. The cat sat on the mat.", {"stock_phrases": [], "hedges": [], "inspect_phrases": []})
    assert matches(result, "repeated_ngrams") == ["the cat sat", "the cat sat"]
    assert spans(result, "repeated_ngrams") == [[0, 11], [13, 24]]
    assert result["features"]["repeated_ngrams"]["count"] == 2


def test_repeated_ngrams_report_overlapping_occurrences():
    result = analyze("go go go go", {"stock_phrases": [], "hedges": [], "inspect_phrases": []})
    # Word 3-grams: (go go go) at words 0-2 and 1-3.
    assert spans(result, "repeated_ngrams") == [[0, 8], [3, 11]]


def test_no_repeats_below_threshold():
    result = analyze("one two three four five six", {"stock_phrases": [], "hedges": [], "inspect_phrases": []})
    assert result["features"]["repeated_ngrams"]["count"] == 0


# --- Metamorphic tests (controlled fixtures, SPEC §8.2) ------------------------------------------------------

BASE = "The committee met on Tuesday. Members reviewed the budget and approved two proposals."


def test_inserting_one_stock_phrase_adds_exactly_one_match(lexicons):
    before = analyze(BASE, lexicons)
    after = analyze("In summary, " + BASE, lexicons)
    assert counts(before) == {"stock_phrases": 0, "hedges": 0, "repeated_ngrams": 0, "inspect_phrases": 0}
    assert counts(after) == {**counts(before), "stock_phrases": 1}


def test_sentence_duplication_adds_calculated_repeated_ngrams(lexicons):
    # Duplicating a k-word sentence adds k-2 repeated 3-grams, each seen twice: 2(k-2) occurrences.
    sentence = "Alpha beta gamma delta epsilon."
    k = 5
    before = analyze(BASE + " " + sentence, lexicons)
    after = analyze(BASE + " " + sentence + " " + sentence, lexicons)
    assert counts(before)["repeated_ngrams"] == 0
    assert counts(after) == {**counts(before), "repeated_ngrams": 2 * (k - 2)}


def test_inserting_studies_show_adds_one_inspect_match_only(lexicons):
    before = analyze(BASE, lexicons)
    after = analyze(BASE.replace("Members reviewed", "Studies show members reviewed"), lexicons)
    assert counts(after) == {**counts(before), "inspect_phrases": 1}


# --- Span integrity ------------------------------------------------------------------------------------------

INTEGRITY_TEXTS = [
    "🌍 In conclusion, studies show that 🌍 it might rain. 🌍 It might rain. It might rain.",
    "Zero\u200bwidth: studies\u200bshow nothing; studies show something. Perhaps\u200b perhaps.",
    "Homoglyph: Studies sh\u043ew (Cyrillic o) versus studies show. Delve into it; d\u0435lve into it.",
    "Unicode “quotes” — it’s worth noting… naïve café résumé; it’s worth noting again. Café naïve résumé café naïve résumé.",
]


@pytest.mark.parametrize("text", INTEGRITY_TEXTS)
def test_span_integrity(text, lexicons):
    result = analyze(text, lexicons)
    for feature in FEATURES:
        f = result["features"][feature]
        assert f["count"] == len(f["spans"]) == len(f["matches"])
        for (start, end), label in zip(f["spans"], f["matches"]):
            surface = text[start:end]
            if feature == "repeated_ngrams":
                assert " ".join(w.lower() for w in WORD_RE.findall(surface)) == label
            else:
                normalized = re.sub(r"\s+", " ", surface).replace("’", "'").lower()
                assert normalized == label.lower()


def test_raw_detector_behavior_on_attack_characters(lexicons):
    result = analyze(INTEGRITY_TEXTS[1], lexicons)
    # The zero-width-joined "studies\u200bshow" does not match; the plain one does.
    assert matches(result, "inspect_phrases") == ["studies show"]
    result = analyze(INTEGRITY_TEXTS[2], lexicons)
    # Cyrillic homoglyphs prevent matches: only the ASCII spellings are found.
    assert matches(result, "inspect_phrases") == ["studies show"]
    assert matches(result, "stock_phrases") == ["delve into"]


def test_emoji_offsets_index_python_string(lexicons):
    text = INTEGRITY_TEXTS[0]
    result = analyze(text, lexicons)
    start, end = spans(result, "stock_phrases")[0]
    assert text[start:end] == "In conclusion" and start == 2


# --- Robustness ----------------------------------------------------------------------------------------------


def test_empty_string(lexicons):
    result = analyze("", lexicons)
    assert result["n_words"] == 0
    for feature in FEATURES:
        assert result["features"][feature] == {"count": 0, "rate": None, "spans": [], "matches": []}


def test_very_long_single_sentence(lexicons):
    text = " ".join(f"w{i}" for i in range(20000)) + " perhaps"
    result = analyze(text, lexicons)
    assert result["n_words"] == 20001
    assert counts(result) == {"stock_phrases": 0, "hedges": 1, "repeated_ngrams": 0, "inspect_phrases": 0}


def test_non_ascii_punctuation(lexicons):
    text = "«Perhaps»—arguably… ¿might? ¡In conclusion!"
    result = analyze(text, lexicons)
    assert matches(result, "hedges") == ["perhaps", "arguably", "might"]
    assert matches(result, "stock_phrases") == ["in conclusion"]
