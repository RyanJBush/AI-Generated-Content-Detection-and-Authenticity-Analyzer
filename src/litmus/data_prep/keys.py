"""CA1 domain-separated selection, split and row keys."""

import hashlib
import json

SELECT = "litmus/r1/select/v1"
SPLIT = "litmus/r1/split/v1"
ROW = "litmus/r1/row/v1"


def canonical(value) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def key(tag: str, seed: int, item_id: str) -> bytes:
    if (
        not isinstance(tag, str)
        or type(seed) is not int
        or not isinstance(item_id, str)
    ):
        raise TypeError("tag/id must be strings and seed an integer (not bool)")
    return hashlib.sha256(canonical([tag, seed, item_id])).digest()


def split_digest(digest: bytes) -> str:
    if len(digest) != 32:
        raise ValueError("expected SHA-256 digest")
    u = int.from_bytes(digest[:8], "big") / 2**64
    return "dev" if u < 0.30 else "test"


def split_source(seed: int, source_id: str) -> str:
    return split_digest(key(SPLIT, seed, source_id))
