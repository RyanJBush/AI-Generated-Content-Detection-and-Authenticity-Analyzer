"""Packaged lexicons: loader and validator (R1-C plan §d).

Lexicons are package data (``litmus/quality/lexicons/<name>.txt``) and are read
only through ``importlib.resources``, once, when a caller loads them (observer
initialization). Nothing here reads files or the network afterwards.

File format: UTF-8 without BOM, LF line endings. The first six lines are
``# key: value`` headers in this order: name, version, author, license, date,
source. After the header, blank lines and lines whose first non-space
character is ``#`` are ignored; every other line, stripped, is one entry.
"""
import datetime
import hashlib
import importlib.resources
import re
import unicodedata
from dataclasses import dataclass
from typing import Tuple

from litmus.quality.words import APOSTROPHES, HYPHENS, WORD

LEXICON_NAMES = ("claim_phrases_to_inspect", "hedges", "stock_phrases")
HEADER_KEYS = ("name", "version", "author", "license", "date", "source")
_HEADER_LINE = re.compile(r"# ([a-z]+): (\S.*)")
_ENTRY = re.compile(rf"{WORD}(?: {WORD})*")
_NAME = re.compile(r"[a-z][a-z0-9_]*")
# Apostrophe and hyphen variants compile to the same pattern, so entries that
# differ only in them are duplicates too
_VARIANTS = str.maketrans({**{c: "'" for c in APOSTROPHES},
                           **{c: "-" for c in HYPHENS}})


class LexiconError(ValueError):
    """A lexicon failed validation; the message is the reason."""


@dataclass(frozen=True)
class Lexicon:
    name: str
    version: int
    author: str
    license: str
    date: str
    source: str
    entries: Tuple[str, ...]
    sha256: str  # of the raw file bytes


def _entry_problem(entry: str):
    if "#" in entry:
        return "contains '#'"
    if any(unicodedata.category(c) in ("Cc", "Cf") for c in entry):
        return "contains a control or format character"
    if not _ENTRY.fullmatch(entry):
        return "is not words separated by single spaces"
    return None


def parse_lexicon(data: bytes, expected_name: str) -> Lexicon:
    """Validate raw lexicon bytes; raises LexiconError with the reason."""
    if data.startswith(b"\xef\xbb\xbf"):
        raise LexiconError("byte order mark present")
    if b"\r" in data:
        raise LexiconError("carriage return present (LF line endings required)")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise LexiconError(f"not UTF-8: {e}") from None
    lines = text.split("\n")
    if len(lines) < len(HEADER_KEYS):
        raise LexiconError("header incomplete")
    header = {}
    for i, key in enumerate(HEADER_KEYS):
        m = _HEADER_LINE.fullmatch(lines[i])
        if not m or m.group(1) != key:
            raise LexiconError(f"header line {i + 1} must be '# {key}: <value>'")
        header[key] = m.group(2).strip()
    if header["name"] != expected_name:
        raise LexiconError(f"header name {header['name']!r} != {expected_name!r}")
    if not re.fullmatch(r"[1-9][0-9]*", header["version"]):
        raise LexiconError("version must be a positive integer")
    try:
        datetime.date.fromisoformat(header["date"])
    except ValueError:
        raise LexiconError("date must be ISO 8601 (YYYY-MM-DD)") from None

    entries, seen = [], {}
    for number, line in enumerate(lines[len(HEADER_KEYS):], len(HEADER_KEYS) + 1):
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        problem = _entry_problem(entry)
        if problem:
            raise LexiconError(f"line {number}: entry {entry!r} {problem}")
        key = entry.casefold().translate(_VARIANTS)
        if key in seen:
            raise LexiconError(f"line {number}: entry {entry!r} duplicates line "
                               f"{seen[key]} (case-insensitive)")
        seen[key] = number
        entries.append(entry)
    if not entries:
        raise LexiconError("no valid entries")
    return Lexicon(name=header["name"], version=int(header["version"]),
                   author=header["author"], license=header["license"],
                   date=header["date"], source=header["source"],
                   entries=tuple(entries), sha256=hashlib.sha256(data).hexdigest())


def resource_bytes(name: str) -> bytes:
    """Raw bytes of a packaged lexicon, via importlib.resources only."""
    if not _NAME.fullmatch(name):
        raise LexiconError(f"invalid lexicon name {name!r}")
    resource = importlib.resources.files("litmus.quality").joinpath(
        "lexicons", f"{name}.txt")
    try:
        return resource.read_bytes()
    except FileNotFoundError:
        raise LexiconError(f"lexicon {name!r} is not packaged") from None


def load_lexicon(name: str) -> Lexicon:
    return parse_lexicon(resource_bytes(name), name)
