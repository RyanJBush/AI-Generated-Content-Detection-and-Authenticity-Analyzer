"""Layer B: rule-based slop-pattern analyzer (SPEC §3.2, reduced MVP features).

Runs on the original text with no normalization; every span is a [start, end) index into that string.
Matching rules:
- Words: WORD_RE (Unicode word characters, with internal ' or ’ apostrophes). Zero-width characters and
  punctuation separate words; homoglyphs are ordinary word characters (raw detector, SPEC §3.4).
- Lexicon entries: case-insensitive, not preceded or followed by a word character; whitespace between entry words
  matches any run of whitespace; ' in an entry also matches ’. Within one feature, overlapping matches are resolved
  leftmost-longest (earliest start, then longest span, then lexicon order).
- Repeated word n-grams: lowercased (str.lower) consecutive word 3-grams, across punctuation and sentence
  boundaries; every occurrence of a 3-gram seen at least twice is reported, including overlapping occurrences.
"""
import re
from collections import Counter
from pathlib import Path

LEXICON_DIR = Path(__file__).resolve().parents[2] / "data" / "lexicons"
LEXICON_FEATURES = {
    "stock_phrases": "stock_phrases.txt",
    "hedges": "hedges.txt",
    "inspect_phrases": "inspect_phrases.txt",
}
FEATURES = ["stock_phrases", "hedges", "repeated_ngrams", "inspect_phrases"]
WORD_RE = re.compile(r"\w+(?:['’]\w+)*")
NGRAM_N = 3


def load_lexicon(path):
    """Entries in file order: one per line, skipping blank lines and # comments."""
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            entry = line.strip()
            if entry and not entry.startswith("#"):
                entries.append(entry)
    return entries


def load_lexicons(directory=LEXICON_DIR):
    return {feature: load_lexicon(Path(directory) / name) for feature, name in LEXICON_FEATURES.items()}


def _entry_pattern(entry):
    words = [re.escape(word).replace("'", "['’]") for word in entry.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def find_lexicon_matches(text, entries):
    """Non-overlapping (start, end, entry) matches, leftmost-longest across entries."""
    candidates = []
    for order, entry in enumerate(entries):
        for m in _entry_pattern(entry).finditer(text):
            candidates.append((m.start(), -(m.end() - m.start()), order, m.end(), entry))
    candidates.sort()
    kept, last_end = [], 0
    for start, _, _, end, entry in candidates:
        if start >= last_end:
            kept.append((start, end, entry))
            last_end = end
    return kept


def find_repeated_ngrams(text, n=NGRAM_N):
    """(start, end, ngram) for every occurrence of each lowercased word n-gram occurring at least twice."""
    words = [(m.start(), m.end(), m.group().lower()) for m in WORD_RE.finditer(text)]
    grams = [
        (words[i][0], words[i + n - 1][1], " ".join(w[2] for w in words[i:i + n]))
        for i in range(len(words) - n + 1)
    ]
    counts = Counter(gram for _, _, gram in grams)
    return [g for g in grams if counts[g[2]] >= 2]


def count_words(text):
    return sum(1 for _ in WORD_RE.finditer(text))


def _feature(matches, n_words):
    return {
        "count": len(matches),
        "rate": 100.0 * len(matches) / n_words if n_words else None,
        "spans": [[start, end] for start, end, _ in matches],
        "matches": [label for _, _, label in matches],
    }


def analyze(text, lexicons=None):
    """Per-feature count, rate per 100 words (None when there are no words), spans and matched entries."""
    if lexicons is None:
        lexicons = load_lexicons()
    n_words = count_words(text)
    features = {name: _feature(find_lexicon_matches(text, lexicons[name]), n_words) for name in LEXICON_FEATURES}
    features["repeated_ngrams"] = _feature(find_repeated_ngrams(text), n_words)
    return {"n_words": n_words, "features": {name: features[name] for name in FEATURES}}
