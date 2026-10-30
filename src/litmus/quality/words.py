"""Word definition and word index (R1-C plan §c).

One regex defines a word for word counts, 3-grams, and lexicon boundaries:

    WORD_CHAR = [^\\W_] or a combining mark in the listed blocks
    JOINER    = ' (U+0027), U+2019, - (U+002D), U+2010, U+2011
    WORD      = WORD_CHAR+ (JOINER WORD_CHAR+)*

Letters and digits of any script are word characters; underscore is not.
Apostrophes and hyphens join two word runs; a leading or trailing one is not
part of the word. Zero-width and format characters (Cf) are not word
characters, so they split words. Scripts written without spaces (e.g. CJK)
form one word per contiguous run. Matching runs on the original string: no
normalization, and spans are [start, end) code-point offsets into it.
"""
import re
from dataclasses import dataclass
from typing import Tuple

# Combining-mark blocks added explicitly: stdlib re's \w excludes marks (Mn)
COMBINING_MARKS = "\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f"
WORD_CHAR = rf"(?:[^\W_]|[{COMBINING_MARKS}])"
APOSTROPHES = "'\u2019"
HYPHENS = "-\u2010\u2011"
JOINER = rf"[{re.escape(APOSTROPHES + HYPHENS)}]"
WORD = rf"{WORD_CHAR}+(?:{JOINER}{WORD_CHAR}+)*"
WORD_RE = re.compile(WORD)


@dataclass(frozen=True)
class WordIndex:
    """Words of one segment text: [start, end) code-point spans, in order."""

    spans: Tuple[Tuple[int, int], ...]

    @property
    def count(self) -> int:
        return len(self.spans)


def word_index(text: str) -> WordIndex:
    return WordIndex(tuple(m.span() for m in WORD_RE.finditer(text)))
