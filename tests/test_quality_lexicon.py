"""R1-C1: packaged lexicons, loader and validator (model-free)."""
import hashlib
import importlib.resources
import pathlib
import re
import subprocess
import sys

import pytest

from litmus.quality import lexicon as lex
from litmus.quality.lexicon import (
    LEXICON_NAMES,
    LexiconError,
    load_lexicon,
    parse_lexicon,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "src" / "litmus" / "quality" / "lexicons"
HEADER = ("# name: test\n# version: 3\n# author: test author\n"
          "# license: OPEN \u2014 pending Ryan's decision\n# date: 2026-10-30\n"
          "# source: test fixture\n")


def parse(body, header=HEADER, name="test"):
    return parse_lexicon((header + body).encode("utf-8"), name)


def test_valid_file_with_blank_and_comment_lines():
    lx = parse("\nperhaps\n\n# a comment\n   # indented comment\n  it seems  \n\n")
    assert lx.entries == ("perhaps", "it seems")
    assert (lx.name, lx.version, lx.date) == ("test", 3, "2026-10-30")
    assert lx.license == "OPEN \u2014 pending Ryan's decision"
    assert lx.author == "test author" and lx.source == "test fixture"


def test_reported_sha256_is_of_the_file_bytes():
    data = (HEADER + "perhaps\n").encode("utf-8")
    assert parse_lexicon(data, "test").sha256 == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("body", ["", "\n\n   \n", "# only\n# comments\n",
                                  "\n# mixed\n\n  # blank and comment\n"])
def test_zero_valid_entries_fail(body):
    with pytest.raises(LexiconError, match="no valid entries"):
        parse(body)


@pytest.mark.parametrize("body", [
    "perhaps\nPerhaps\n",
    "it seems\nIT SEEMS\n",
    "in today's world\nin today\u2019s world\n",  # apostrophe variants match alike
    "ever-evolving\never\u2010evolving\n",  # hyphen variants match alike
])
def test_case_insensitive_duplicates_fail(body):
    with pytest.raises(LexiconError, match="duplicates line"):
        parse(body)


@pytest.mark.parametrize("header, reason", [
    ("", "header incomplete"),
    (HEADER.replace("# name: test", "name: test"), "header line 1"),
    (HEADER.replace("# version: 3\n# author: test author\n",
                    "# author: test author\n# version: 3\n"), "header line 2"),
    (HEADER.replace("# name: test", "# name: other"), "header name"),
    (HEADER.replace("# version: 3", "# version: v1"), "positive integer"),
    (HEADER.replace("# version: 3", "# version: 0"), "positive integer"),
    (HEADER.replace("2026-10-30", "30/10/2026"), "ISO 8601"),
    (HEADER.replace("# source: test fixture", "# source:"), "header line 6"),
])
def test_header_parsing(header, reason):
    with pytest.raises(LexiconError, match=reason):
        parse("perhaps\n", header=header)


@pytest.mark.parametrize("entry, reason", [
    ("per#haps", "'#'"),
    ("per\u200bhaps", "control or format"),
    ("it\tseems", "control or format"),
    ("it  seems", "single spaces"),
    ("--", "single spaces"),
    ("studies show.", "single spaces"),
    ("snake_case", "single spaces"),
])
def test_invalid_entries_fail(entry, reason):
    with pytest.raises(LexiconError, match=reason):
        parse(entry + "\n")


@pytest.mark.parametrize("data, reason", [
    (b"\xef\xbb\xbf" + HEADER.encode() + b"perhaps\n", "byte order mark"),
    (HEADER.replace("\n", "\r\n").encode() + b"perhaps\r\n", "carriage return"),
    (HEADER.encode() + b"caf\xe9\n", "not UTF-8"),
])
def test_encoding_rules(data, reason):
    with pytest.raises(LexiconError, match=reason):
        parse_lexicon(data, "test")


def test_loading_goes_through_importlib_resources(monkeypatch):
    calls = []
    real = importlib.resources.files

    def spy(package):
        calls.append(package)
        return real(package)

    monkeypatch.setattr(lex.importlib.resources, "files", spy)
    assert load_lexicon("hedges").entries
    assert calls == ["litmus.quality"]


@pytest.mark.parametrize("name", ["../hedges", "Hedges", "", "hedges.txt"])
def test_resource_names_are_restricted(name):
    with pytest.raises(LexiconError, match="invalid lexicon name"):
        load_lexicon(name)


def test_missing_resource_is_a_lexicon_error():
    with pytest.raises(LexiconError, match="not packaged"):
        load_lexicon("no_such_lexicon")


# --- committed lexicons ---

def _recorded_hashes():
    """SHA-256 values recorded in docs/decisions.md (R1-C1 lexicon table)."""
    text = (ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
    rows = re.findall(r"\| `([a-z_]+)\.txt` \| (\d+) \| (\d+) \| `([0-9a-f]{64})` \|",
                      text)
    return {name: (int(v), int(n), sha) for name, v, n, sha in rows}


def test_packaged_resource_names_are_exact():
    found = sorted(p.name for p in importlib.resources.files("litmus.quality")
                   .joinpath("lexicons").iterdir() if p.name.endswith(".txt"))
    assert found == [f"{n}.txt" for n in LEXICON_NAMES]


@pytest.mark.parametrize("name", LEXICON_NAMES)
def test_committed_lexicons_validate_and_match_recorded_hashes(name):
    lx = load_lexicon(name)
    source = (SOURCE_DIR / f"{name}.txt").read_bytes()
    assert lx.sha256 == hashlib.sha256(source).hexdigest()
    assert _recorded_hashes()[name] == (lx.version, len(lx.entries), lx.sha256)
    assert lx.version == 1
    assert lx.license == "OPEN \u2014 pending Ryan's decision"
    assert lx.author == ("drafted with AI assistance (Claude Code) for the "
                         "Litmus project; reviewed by Ryan")


def test_hedges_omit_may():
    assert "may" not in {e.casefold() for e in load_lexicon("hedges").entries}


# --- import isolation (C1 scope) ---

ISOLATION = r"""
import sys
import litmus
import litmus.quality
import litmus.quality.lexicon as lexicon
import litmus.quality.matcher as matcher
import litmus.quality.words as words
for name in lexicon.LEXICON_NAMES:
    lx = lexicon.load_lexicon(name)
    pattern = matcher.compile_entries(lx.entries)
    matcher.find_spans(pattern, "it seems that studies show")
words.word_index("it seems")
bad = sorted(m for m in sys.modules
             if m.split(".")[0] in ("torch", "transformers")
             or m == "litmus.scorer" or m.startswith("litmus.scorer."))
print(bad)
sys.exit(1 if bad else 0)
"""


def test_c1_modules_do_not_import_the_model_stack():
    # Fresh interpreter (tests may spawn processes; analysis code may not)
    proc = subprocess.run([sys.executable, "-I", "-c", ISOLATION],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert proc.stdout.strip() == "[]"
