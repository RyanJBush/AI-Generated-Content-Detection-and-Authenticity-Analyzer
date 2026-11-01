"""Synthetic-only selection, text, deduplication and manifest invariants."""

import csv
import dataclasses
import hashlib
import json
import random

import pytest

from litmus.data_prep.acquisition import PrepError
from litmus.data_prep.cleanup import cleanup
from litmus.data_prep.keys import ROW, key
from litmus.data_prep.schema import COLUMNS, Meta, iter_csv, metadata
from litmus.data_prep.selection import attach_attacks, select_groups
from litmus.data_prep.text import assess


def row(identifier, source, model="human", attack="none", parent=None, domain="news"):
    return Meta(
        identifier,
        source,
        parent or identifier,
        model,
        "" if model == "human" else "greedy",
        "" if model == "human" else "no",
        attack,
        domain,
    )


def population(n=12):
    rows = []
    for i in range(n):
        source = f"source-{i}"
        rows += [
            row(f"h{i}", source),
            row(f"a{i}", source, "gpt2"),
            row(f"b{i}", source, "gpt3"),
        ]
    return rows


def test_source_unique_round_robin_no_reallocation_and_order_independence():
    rows = population()
    groups, stats = select_groups(rows, seed=20261030, target=10)
    random.Random(45).shuffle(rows)
    again, counts = select_groups(rows, seed=20261030, target=10)
    assert groups == again and stats == counts
    assert len(groups) == len({g["source_id"] for g in groups}) == 10
    assert [c["assigned"] for c in stats["cells"]] == [5, 5]
    tiny, counts = select_groups(population(1), target=4)
    assert len(tiny) == 1
    assert sum(c["shortfall"] for c in counts["cells"]) == 3


def test_machine_and_attack_tie_break_has_no_content_input():
    rows = population(1)
    rows += [row("extra", "source-0", "gpt2")]
    groups, _ = select_groups(rows, target=1)
    group = groups[0]
    assert group["machine_id"] == min(
        ["a0", "extra"], key=lambda x: (key(ROW, 20261030, x), x)
    )
    parent = group["machine_id"]
    attacks = [row(i, "source-0", "gpt2", "paraphrase", parent) for i in ("x", "y")]
    attacks += [row("bad", "other-source", "gpt2", "homoglyph", parent)]
    attached, rejected, stats = attach_attacks(rows + attacks, groups)
    assert attached[0]["attack_ids"]["paraphrase"] == min(
        ["x", "y"], key=lambda x: (key(ROW, 20261030, x), x)
    )
    assert {r["id"] for r in rejected} == {"bad", "x", "y"} - set(
        attached[0]["attack_ids"].values()
    )
    assert stats["mismatched_attacks"] == 1


def test_metadata_projection_does_not_access_generation():
    class Poison(dict):
        def __getitem__(self, item):
            if item in ("generation", "title", "prompt"):
                pytest.fail("selection read content")
            return super().__getitem__(item)

    item = row("h", "s")
    assert metadata(Poison(dataclasses.asdict(item))) == item


def test_csv_quotes_newlines_and_missing_columns(tmp_path):
    path = tmp_path / "input.csv"
    values = dataclasses.asdict(row("h", "s"))
    values.update(title="", prompt="", generation='quoted, "text"\r\nsecond line')
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, COLUMNS)
        writer.writeheader()
        writer.writerow(values)
    assert list(iter_csv(path))[0]["generation"] == values["generation"]
    path.write_text("id,generation\na,b\n", encoding="utf-8")
    with pytest.raises(PrepError):
        list(iter_csv(path))
    path.write_bytes(b"\xff")
    with pytest.raises((UnicodeDecodeError, PrepError)):
        list(iter_csv(path))


class StubTokenizer:
    def __call__(self, text, **kwargs):
        assert kwargs["add_special_tokens"] is False
        assert kwargs["split_special_tokens"] is True
        return {
            "input_ids": [ord(c) for c in text],
            "offset_mapping": [(i, i + 1) for i in range(len(text))],
        }


@pytest.mark.parametrize(
    "length,accepted,scored",
    [(63, False, 63), (64, True, 64), (512, True, 512), (513, True, 512)],
)
def test_text_boundaries_and_unambiguous_window_hash(length, accepted, scored):
    observed, errors = assess("a" * length, StubTokenizer())
    assert (not errors) == accepted
    assert observed["tokens_scored"] == scored
    expected = json.dumps([97] * scored, separators=(",", ":")).encode()
    assert observed["scored_window_sha256"] == hashlib.sha256(expected).hexdigest()


@pytest.mark.parametrize(
    "text,reason",
    [
        ("a" * 63 + "\0", "nul"),
        ("\x01" + "a" * 99, "control_share"),
        (" " * 100, "whitespace_only"),
        ("a" * 200001, "text_too_long"),
    ],
    ids=["nul", "control", "whitespace", "overlong"],
)
def test_text_exclusions(text, reason):
    _, errors = assess(text, StubTokenizer())
    assert reason in errors


def test_unicode_and_newlines_are_preserved():
    text = "a\u200b\u0430\r\n" * 30
    result, errors = assess(text, StubTokenizer())
    assert not errors
    assert result["raw_text_sha256"] == hashlib.sha256(text.encode()).hexdigest()


def entry(identifier, source, role, raw, window, parent=None):
    return {
        "id": identifier,
        "source_id": source,
        "role": role,
        "raw_text_sha256": raw,
        "scored_window_sha256": window,
        "adv_source_id": parent or identifier,
        "split": "dev",
        "attack": "none" if role != "attack" else "paraphrase",
        "domain": "news",
        "model": "human" if role == "human" else "gpt2",
    }


def test_collision_removes_every_cross_group_participant_then_pairs():
    rows = [
        entry("h1", "s1", "human", "shared", "h1"),
        entry("m1", "s1", "machine", "m1", "m1"),
        entry("a1", "s1", "attack", "a1", "a1", "m1"),
        entry("h2", "s2", "human", "shared", "h2"),
        entry("m2", "s2", "machine", "m2", "m2"),
    ]
    groups = [
        {"source_id": "s1", "human_id": "h1", "machine_id": "m1"},
        {"source_id": "s2", "human_id": "h2", "machine_id": "m2"},
    ]
    kept, excluded, collisions, noops = cleanup(rows, groups, [])
    assert kept == []
    assert {r["id"] for r in excluded} == {r["id"] for r in rows}
    assert collisions[0]["row_ids"] == ["h1", "h2"]
    assert not noops


def test_window_collision_across_splits_and_within_group_noop():
    rows = [
        entry("h1", "s1", "human", "h1", "h1"),
        entry("m1", "s1", "machine", "m1", "w"),
        entry("a1", "s1", "attack", "m1", "w", "m1"),
        entry("h2", "s2", "human", "h2", "h2"),
        entry("m2", "s2", "machine", "m2", "other"),
    ]
    groups = [
        {"source_id": "s1", "human_id": "h1", "machine_id": "m1"},
        {"source_id": "s2", "human_id": "h2", "machine_id": "m2"},
    ]
    kept, _, _, noops = cleanup(rows, groups, [])
    assert len(kept) == 5 and noops[0]["raw_noop"] and noops[0]["window_noop"]
    rows[-1]["scored_window_sha256"] = "w"
    rows[-1]["split"] = "test"
    kept, excluded, collisions, _ = cleanup(rows, groups, [])
    assert not kept and len(excluded) == 5
    assert any(c["channel"] == "scored_window_sha256" for c in collisions)


def test_other_within_group_equalities_are_audited_without_extra_exclusion():
    from litmus.data_prep.cleanup import within_group_equalities

    rows = [
        entry("h", "s", "human", "same", "window"),
        entry("m", "s", "machine", "same", "window"),
    ]
    groups = [{"source_id": "s", "human_id": "h", "machine_id": "m"}]
    kept, excluded, collisions, noops = cleanup(rows, groups, [])
    assert len(kept) == 2 and not excluded and not collisions and not noops
    flags = within_group_equalities(kept)
    assert len(flags) == 2
    assert all(flag["row_ids"] == ["h", "m"] for flag in flags)
