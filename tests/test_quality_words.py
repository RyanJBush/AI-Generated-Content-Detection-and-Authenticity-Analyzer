"""R1-C1: word definition and word index (model-free)."""
import pytest

from litmus.quality.words import word_index


def words(text):
    idx = word_index(text)
    for start, end in idx.spans:
        assert 0 <= start < end <= len(text)
    return [text[s:e] for s, e in idx.spans]


@pytest.mark.parametrize("text, expected", [
    ("The cat sat.", ["The", "cat", "sat"]),
    ("don't and don\u2019t", ["don't", "and", "don\u2019t"]),
    ("'quoted' and dogs'", ["quoted", "and", "dogs"]),  # edge apostrophes excluded
    ("ever-evolving well\u2010known non\u2011stop", ["ever-evolving",
                                                    "well\u2010known",
                                                    "non\u2011stop"]),
    ("a -- b, -x- c-", ["a", "b", "x", "c"]),  # no joiner at either edge
    ("en\u2013dash em\u2014dash", ["en", "dash", "em", "dash"]),  # dashes split
    ("in 2024, 3.14 and 4th", ["in", "2024", "3", "14", "and", "4th"]),
    ("snake_case", ["snake", "case"]),  # underscore separates
    ("\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440",
     ["\u041f\u0440\u0438\u0432\u0435\u0442", "\u043c\u0438\u0440"]),  # Cyrillic
    ("\u4e2d\u6587\u6587\u672c test", ["\u4e2d\u6587\u6587\u672c", "test"]),  # CJK
    ("Stra\u00dfe STRA\u1e9eE", ["Stra\u00dfe", "STRA\u1e9eE"]),
])
def test_word_spans(text, expected):
    assert words(text) == expected


def test_exact_spans_and_count():
    idx = word_index("  Hi, there-you go ")
    assert idx.spans == ((2, 4), (6, 15), (16, 18))
    assert idx.count == 3


def test_emoji_offsets_are_code_points():
    text = "\U0001F600 hi \U0001F469\u200d\U0001F4BB yo"  # emoji, ZWJ sequence
    idx = word_index(text)
    assert [text[s:e] for s, e in idx.spans] == ["hi", "yo"]
    # ZWJ sequence = 3 code points (U+1F469, U+200D, U+1F4BB) at 5..7
    assert idx.spans == ((2, 4), (9, 11))


def test_combining_marks_stay_in_the_word():
    text = "cafe\u0301 ok"  # decomposed e + COMBINING ACUTE ACCENT
    assert words(text) == ["cafe\u0301", "ok"]


def test_zero_width_space_splits_words():
    assert words("wo\u200brd") == ["wo", "rd"]


def test_homoglyph_is_still_one_word():
    # Cyrillic "о" (U+043E) inside Latin letters: still word characters
    assert words("sh\u043ew me") == ["sh\u043ew", "me"]


@pytest.mark.parametrize("text", ["", "   ", "\n\t \u3000", "... !!! --", "_ _"])
def test_no_words(text):
    idx = word_index(text)
    assert idx.count == 0 and idx.spans == ()


def test_no_normalization():
    nfc, nfd = "caf\u00e9", "cafe\u0301"
    assert word_index(nfc).spans == ((0, 4),)
    assert word_index(nfd).spans == ((0, 5),)
