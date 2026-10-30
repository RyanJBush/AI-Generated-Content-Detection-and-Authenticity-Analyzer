"""Lexicon entry compiler (R1-C plan §c).

Each lexicon compiles to one case-insensitive pattern that runs with
``finditer`` on the ORIGINAL text, so match offsets are offsets into it; no
lowered or casefolded copy is ever matched (casefolding can change length,
e.g. "ß" -> "ss"). ``re.IGNORECASE`` uses simple case folding, which never
changes length, so full-folding equivalents such as "ß"/"SS" do not match.

Entry -> pattern: a space matches ``\\s+``; an apostrophe matches either
apostrophe; a hyphen matches any listed hyphen; everything else is literal.
Contractions match only when listed: there is no expansion.

Leftmost-longest, non-overlapping: alternatives are ordered by word count
descending, then character length descending, then casefolded text, then raw
text. ``finditer`` returns the leftmost match, and at a given start the first
matching alternative wins. An entry with more words always covers more text
when two entries match at the same start, because every entry word must end
at whitespace or at the entry's end boundary.
"""
import re
from typing import Iterable, List, Pattern

from litmus.quality.words import APOSTROPHES, HYPHENS, JOINER, WORD_CHAR

# A match never starts or ends inside a WORD (fixed-width lookarounds)
_BEFORE = rf"(?<!{WORD_CHAR})(?<!{WORD_CHAR}{JOINER})"
_AFTER = rf"(?!{WORD_CHAR})(?!{JOINER}{WORD_CHAR})"
_APOSTROPHE = f"[{re.escape(APOSTROPHES)}]"
_HYPHEN = f"[{re.escape(HYPHENS)}]"


def entry_pattern(entry: str) -> str:
    """Regex source for one validated entry (words separated by single spaces)."""
    def char(c):
        if c in APOSTROPHES:
            return _APOSTROPHE
        if c in HYPHENS:
            return _HYPHEN
        return re.escape(c)

    return r"\s+".join("".join(char(c) for c in word) for word in entry.split(" "))


def entry_order_key(entry: str):
    """Longest-first ordering; ties broken deterministically."""
    return (-len(entry.split(" ")), -len(entry), entry.casefold(), entry)


def compile_entries(entries: Iterable[str]) -> Pattern[str]:
    ordered = sorted(set(entries), key=entry_order_key)
    if not ordered:
        raise ValueError("no entries to compile")
    alternatives = "|".join(entry_pattern(e) for e in ordered)
    return re.compile(f"{_BEFORE}(?:{alternatives}){_AFTER}", re.IGNORECASE)


def find_spans(pattern: Pattern[str], text: str) -> List[List[int]]:
    """Non-overlapping matches, left to right, as [start, end) on ``text``."""
    return [[m.start(), m.end()] for m in pattern.finditer(text)]
