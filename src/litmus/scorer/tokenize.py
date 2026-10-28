"""Text preprocessing for the scorer (Addendum A4/A5; policy in litmus.config).

The decoded text from ingestion is tokenized once with the observer tokenizer,
with add_special_tokens and split_special_tokens passed explicitly, then
right-truncated to MAX_TOKENS. Character offsets are code-point offsets into
the decoded string (the segment's text_codepoints frame).
"""
from dataclasses import dataclass
from typing import Any, Dict, List

from litmus import config


@dataclass
class TokenWindow:
    ids: List[int]  # the scored window, len <= MAX_TOKENS
    tokens_total: int  # before truncation
    scored_char_end: int  # end (exclusive) of the window in the decoded text

    @property
    def tokens_scored(self) -> int:
        return len(self.ids)

    @property
    def truncated(self) -> bool:
        return self.tokens_total > len(self.ids)

    def scored_window(self) -> Dict[str, Any]:
        """Addendum A5 details.scored_window."""
        return {
            "tokens_total": self.tokens_total,
            "tokens_scored": self.tokens_scored,
            "truncated": self.truncated,
            "scored_char_range": [0, self.scored_char_end],
        }


def tokenize_window(tokenizer, text: str) -> TokenWindow:
    enc = tokenizer(
        text,
        add_special_tokens=config.ADD_SPECIAL_TOKENS,
        split_special_tokens=config.SPLIT_SPECIAL_TOKENS,
        return_offsets_mapping=True,
    )
    ids = list(enc["input_ids"])
    offsets = list(enc["offset_mapping"])
    if config.TRUNCATION_SIDE != "right":
        raise ValueError(f"unsupported truncation side {config.TRUNCATION_SIDE!r}")
    window = ids[: config.MAX_TOKENS]
    # Byte-level BPE can split one code point across tokens; take the largest
    # end offset in the window so a partially covered character is included.
    end = max((e for _, e in offsets[: len(window)]), default=0)
    return TokenWindow(ids=window, tokens_total=len(ids), scored_char_end=end)
