"""Text quality observers (R1-C2; SPEC §4.3, §8.3; docs/plans/R1-C-PLAN.md).

Each observer turns one decoded segment text (plus its word index) into one
QualityObservation. Observers never see or change origin evidence, and
quality observations do not establish AI origin.

Lexicons are loaded once, when an observer is constructed; ``observe`` does no
file or network access. A lexicon that fails to load (LexiconError, or OSError
and its subclasses) makes only that observer emit an ``error`` record. Every
observer runs in its own try/except (``observe_all``): a failure becomes that
observer's ``error`` record and does not affect the others.

Notes use a fixed ``key=value`` format, in this order: observer_version, then
lexicon_name / lexicon_version / lexicon_sha256 (lexicon observers), then
spans_truncated / spans_reported, then observer-specific notes (claim label;
error / lexicon_invalid on errors).
"""
from collections import Counter
from typing import List, Optional, Sequence

from litmus.quality.lexicon import Lexicon, LexiconError, load_lexicon
from litmus.quality.matcher import compile_entries, find_spans
from litmus.quality.words import WordIndex, word_index
from litmus.schemas import QualityObservation, QualityStatus

OBSERVER_VERSION = "1"
SPAN_CAP = 1000
OBSERVER_IDS = ("stock_phrases", "hedges", "repeated_word_3grams",
                "claim_phrases_to_inspect")
CLAIM_LABEL = "label=phrase to inspect; not evidence that a claim is unsupported"


def _rate(count: int, words: WordIndex) -> Optional[float]:
    return count / words.count * 100 if words.count else None


def _record(observer_id: str, count: int, spans: List[List[int]],
            words: WordIndex, lexicon_notes: Sequence[str] = (),
            extra_notes: Sequence[str] = ()) -> QualityObservation:
    reported = spans[:SPAN_CAP]
    return QualityObservation(
        observer_id=observer_id,
        observer_version=OBSERVER_VERSION,
        status=QualityStatus.OBSERVED if count else QualityStatus.NONE_FOUND,
        count=count,
        rate_per_100_words=_rate(count, words),
        spans=reported,
        notes=[f"observer_version={OBSERVER_VERSION}", *lexicon_notes,
               f"spans_truncated={'true' if len(spans) > SPAN_CAP else 'false'}",
               f"spans_reported={len(reported)}", *extra_notes],
    )


def error_record(observer_id: str, notes: Sequence[str]) -> QualityObservation:
    return QualityObservation(
        observer_id=observer_id, observer_version=OBSERVER_VERSION,
        status=QualityStatus.ERROR, count=None, rate_per_100_words=None,
        spans=[], notes=[f"observer_version={OBSERVER_VERSION}", *notes])


def _lexicon_notes(lexicon: Lexicon) -> List[str]:
    return [f"lexicon_name={lexicon.name}", f"lexicon_version={lexicon.version}",
            f"lexicon_sha256={lexicon.sha256}"]


class LexiconObserver:
    """Leftmost-longest, non-overlapping matches of one packaged lexicon."""

    def __init__(self, observer_id: str, extra_notes: Sequence[str] = ()):
        self.observer_id = observer_id
        self.extra_notes = list(extra_notes)
        self.lexicon: Optional[Lexicon] = None
        self.init_error: Optional[str] = None
        try:
            self.lexicon = load_lexicon(observer_id)
            self.pattern = compile_entries(self.lexicon.entries)
        except LexiconError as e:
            self.init_error = f"lexicon_invalid={e}"
        except OSError as e:  # e.g. PermissionError: isolated to this observer
            self.init_error = f"error={type(e).__name__}"

    def observe(self, text: str, words: WordIndex) -> QualityObservation:
        if self.init_error:
            return error_record(self.observer_id, [self.init_error])
        spans = find_spans(self.pattern, text)
        return _record(self.observer_id, len(spans), spans, words,
                       _lexicon_notes(self.lexicon), self.extra_notes)


class RepeatedWord3Grams:
    """Every occurrence of a word 3-gram whose casefolded key occurs >= 2 times.

    3-grams are consecutive words of the word index, so they cross punctuation
    and line breaks; there is no stop-word filtering. Casefolding builds the
    dictionary key only; spans come from the word index on the original text.
    """

    observer_id = "repeated_word_3grams"

    def observe(self, text: str, words: WordIndex) -> QualityObservation:
        folded = [text[s:e].casefold() for s, e in words.spans]
        keys = [tuple(folded[i:i + 3]) for i in range(len(folded) - 2)]
        repeated = {k for k, n in Counter(keys).items() if n >= 2}
        spans = [[words.spans[i][0], words.spans[i + 2][1]]
                 for i, k in enumerate(keys) if k in repeated]
        return _record(self.observer_id, len(spans), spans, words)


def build_observers() -> list:
    """The four R1 observers, in report order; lexicons load here."""
    return [
        LexiconObserver("stock_phrases"),
        LexiconObserver("hedges"),
        RepeatedWord3Grams(),
        LexiconObserver("claim_phrases_to_inspect", [CLAIM_LABEL]),
    ]


def observe_all(text: str, observers: Sequence) -> List[QualityObservation]:
    """Run every observer on one text; each failure is isolated to its record."""
    words = word_index(text)
    records = []
    for observer in observers:
        try:
            records.append(observer.observe(text, words))
        except Exception as e:  # isolated: never affects other observers
            records.append(error_record(observer.observer_id,
                                        [f"error={type(e).__name__}"]))
    return records
