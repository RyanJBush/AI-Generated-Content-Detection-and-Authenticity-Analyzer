"""R1-C1: lexicon entry compiler (model-free)."""
import pytest

from litmus.quality.lexicon import LEXICON_NAMES, load_lexicon
from litmus.quality.matcher import compile_entries, entry_order_key, find_spans


def matches(entries, text):
    spans = find_spans(compile_entries(entries), text)
    for start, end in spans:
        assert 0 <= start < end <= len(text)
    # non-overlapping, left to right
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    return [text[s:e] for s, e in spans], spans


def test_case_insensitive_on_the_original_string():
    got, spans = matches(["it is important"], "x IT Is IMPORTANT y")
    assert got == ["IT Is IMPORTANT"] and spans == [[2, 17]]


def test_sharp_s_has_no_offset_drift():
    # Simple case folding: "ß" matches "ẞ" (same length) but never "SS"
    got, spans = matches(["stra\u00dfe"], "STRA\u1e9eE strasse STRASSE stra\u00dfe")
    assert got == ["STRA\u1e9eE", "stra\u00dfe"]
    assert spans == [[0, 6], [23, 29]]


def test_turkish_dotted_capital_i_has_no_offset_drift():
    text = "\u0130T SEEMS"  # "İ".lower() has length 2; matching never lowers
    got, spans = matches(["it seems"], text)
    assert spans == [[0, 8]] and got == [text]


@pytest.mark.parametrize("text, expected", [
    ("perhaps", ["perhaps"]),
    ("Perhaps, not", ["Perhaps"]),
    ('"perhaps"', ["perhaps"]),
    ("perhapsx", []),
    ("xperhaps", []),
    ("perhaps-not", []),  # joined by a hyphen: one word
    ("perhaps's", []),  # joined by an apostrophe: one word
    ("perhaps_", ["perhaps"]),  # underscore is not a word character
    ("perhaps2", []),  # digits are word characters
    ("perhaps\u0301", []),  # combining mark continues the word
    ("per\u200bhaps", []),  # zero-width space breaks the entry
    ("p\u0435rhaps", []),  # Cyrillic "е" homoglyph: no match, no crash
])
def test_word_boundaries(text, expected):
    assert matches(["perhaps"], text)[0] == expected


def test_whitespace_runs_inside_entries():
    got, _ = matches(["it seems"], "it   seems\nit\tseems it\u00a0seems it\u200bseems")
    assert got == ["it   seems", "it\tseems", "it\u00a0seems"]


def test_leftmost_longest_with_overlapping_entries():
    entries = ["it is important", "it is important to note", "important"]
    got, spans = matches(entries, "it is important to note that it is important")
    assert got == ["it is important to note", "it is important"]
    assert spans == [[0, 23], [29, 44]]


def test_non_overlapping_left_to_right():
    # "it seems" starts first and wins; "seems to" overlaps it and is skipped
    got, _ = matches(["it seems", "seems to"], "it seems to work; seems to")
    assert got == ["it seems", "seems to"]


def test_adjacent_entries_both_match():
    got, _ = matches(["perhaps", "possibly"], "perhaps possibly")
    assert got == ["perhaps", "possibly"]


def test_contractions_match_only_when_listed():
    text = "it is important to note; it's important to note"
    assert matches(["it is important to note"], text)[0] == [
        "it is important to note"]
    both = ["it is important to note", "it's important to note"]
    assert matches(both, text)[0] == ["it is important to note",
                                      "it's important to note"]
    # A listed apostrophe matches either apostrophe character
    assert matches(["it's important"], "it\u2019s important")[0] == [
        "it\u2019s important"]


def test_hyphen_variants_match():
    assert matches(["ever-evolving"], "ever\u2010evolving ever-evolving")[0] == [
        "ever\u2010evolving", "ever-evolving"]


def test_regex_metacharacters_in_entries_are_literal():
    # Entries are validated as words, but the compiler escapes regardless
    assert matches(["a.b"], "a.b axb")[0] == ["a.b"]


def test_entry_order_is_longest_first_and_deterministic():
    entries = ["b", "a b c", "aa b", "a b", "A b"]
    assert sorted(entries, key=entry_order_key) == ["a b c", "aa b", "A b", "a b",
                                                    "b"]


@pytest.mark.parametrize("name", LEXICON_NAMES)
def test_committed_lexicons_compile_and_match_themselves(name):
    lx = load_lexicon(name)
    pattern = compile_entries(lx.entries)
    for entry in lx.entries:
        text = f"x {entry.upper()} y"
        spans = find_spans(pattern, text)
        assert len(spans) == 1
        assert text[spans[0][0]:spans[0][1]] == entry.upper()


def test_no_entries_is_an_error():
    with pytest.raises(ValueError):
        compile_entries([])
