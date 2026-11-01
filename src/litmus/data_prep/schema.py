"""CSV structure and content-free metadata projection."""

import csv
import sqlite3
from collections import Counter
from dataclasses import dataclass

from litmus.data_prep.acquisition import PrepError

FIELDS = (
    "id",
    "source_id",
    "adv_source_id",
    "model",
    "decoding",
    "repetition_penalty",
    "attack",
    "domain",
)
COLUMNS = (*FIELDS, "title", "prompt", "generation")
DOMAINS = frozenset(
    ("abstracts", "books", "news", "poetry", "recipes", "reddit", "reviews", "wiki")
)
MODELS = frozenset(
    (
        "chatgpt",
        "gpt4",
        "gpt3",
        "gpt2",
        "llama-chat",
        "mistral",
        "mistral-chat",
        "mpt",
        "mpt-chat",
        "cohere",
        "cohere-chat",
    )
)
ATTACKS = frozenset(("paraphrase", "homoglyph", "zero_width_space"))


@dataclass(frozen=True)
class Meta:
    id: str
    source_id: str
    adv_source_id: str
    model: str
    decoding: str
    repetition_penalty: str
    attack: str
    domain: str


def metadata(row):
    values = [row[name] for name in FIELDS]
    if any(not isinstance(v, str) or len(v) > 256 for v in values):
        raise PrepError("invalid_metadata_type_or_length")
    if not values[0] or not values[1]:
        raise PrepError("missing_row_or_source_identity")
    return Meta(*values)


def iter_csv(path):
    csv.field_size_limit(16 * 1024 * 1024)
    with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if (
            not reader.fieldnames
            or len(reader.fieldnames) != len(COLUMNS)
            or set(reader.fieldnames) != set(COLUMNS)
        ):
            raise PrepError("unexpected_csv_schema")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise PrepError("malformed_csv_record")
            yield row


def index_metadata(path, database, budget):
    with path.open("rb") as source:
        file_bom = source.read(3) == b"\xef\xbb\xbf"
    if database.exists():
        raise PrepError("metadata_index_already_exists")
    database.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database)
    db.execute("PRAGMA cache_size=-65536")
    db.execute("PRAGMA temp_store=MEMORY")
    db.execute(
        "CREATE TABLE rows (id TEXT PRIMARY KEY,"
        + ",".join(f"{name} TEXT NOT NULL" for name in FIELDS[1:])
        + ")"
    )
    counts = {
        name: Counter()
        for name in ("domain", "model", "attack", "decoding", "repetition_penalty")
    }
    total, batch = 0, []
    try:
        for raw in iter_csv(path):
            item = metadata(raw)  # does not inspect generation/title/prompt
            batch.append(tuple(getattr(item, f) for f in FIELDS))
            for name in counts:
                counts[name][getattr(item, name)] += 1
            total += 1
            if len(batch) == 10000:
                budget.check_storage(64 * 1024 * 1024)
                db.executemany("INSERT INTO rows VALUES (?,?,?,?,?,?,?,?)", batch)
                db.commit()
                batch.clear()
                if total % 250000 == 0:
                    print(f"Indexed {total:,} metadata rows", flush=True)
        db.executemany("INSERT INTO rows VALUES (?,?,?,?,?,?,?,?)", batch)
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        raise PrepError(
            "duplicate_row_identity; index retained for inspection"
        ) from None
    except Exception:
        db.close()
        raise
    print(f"Metadata EOF: {total:,} rows", flush=True)
    return db, {
        "utf8_file_bom": file_bom,
        "rows_scanned": total,
        "eof": True,
        "categories": {name: dict(value) for name, value in counts.items()},
    }


def indexed_rows(db, *, clean=False):
    query = "SELECT " + ",".join(FIELDS) + " FROM rows"
    if clean:
        query += " WHERE attack='none'"
    for values in db.execute(query):
        yield Meta(*values)
