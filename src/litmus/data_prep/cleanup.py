"""Cross-group exact deduplication and ordered, non-refilling pair cleanup."""

from collections import defaultdict


def within_group_equalities(rows):
    flags = []
    for channel in ("raw_text_sha256", "scored_window_sha256"):
        index = defaultdict(list)
        for row in rows:
            index[row["source_id"], row[channel]].append(row["id"])
        flags += [
            {
                "source_id": sid,
                "channel": channel,
                "sha256": digest,
                "row_ids": sorted(ids),
            }
            for (sid, digest), ids in sorted(index.items())
            if len(ids) > 1
        ]
    return flags


def cleanup(rows, groups, prior_exclusions):
    rejected = {r["id"]: dict(r) for r in prior_exclusions}
    collisions = []
    removed = set()
    for channel in ("raw_text_sha256", "scored_window_sha256"):
        index = defaultdict(list)
        for row in rows:
            index[row[channel]].append(row)
        for digest, matches in sorted(index.items()):
            if len({r["source_id"] for r in matches}) > 1:
                collisions.append(
                    {
                        "channel": channel,
                        "sha256": digest,
                        "row_ids": sorted(r["id"] for r in matches),
                        "source_ids": sorted({r["source_id"] for r in matches}),
                    }
                )
                for row in matches:
                    removed.add(row["id"])
                    exclusion = rejected.setdefault(
                        row["id"],
                        {
                            "id": row["id"],
                            "source_id": row["source_id"],
                            "stage": "collision",
                            "reasons": [],
                        },
                    )
                    exclusion["reasons"].append(channel + "_collision")
    survivors = {r["id"] for r in rows} - removed
    bad_groups = {}
    for group in groups:
        missing = [
            name for name in ("human_id", "machine_id") if group[name] not in survivors
        ]
        if missing:
            bad_groups[group["source_id"]] = missing
    kept = []
    for row in rows:
        if row["id"] in removed:
            continue
        if row["source_id"] in bad_groups:
            missing = bad_groups[row["source_id"]]
            reasons = ["missing_clean_pair"] + ["removed_" + name for name in missing]
            if row["role"] == "attack" and "machine_id" in missing:
                reasons.append("parent_removed")
            rejected[row["id"]] = {
                "id": row["id"],
                "source_id": row["source_id"],
                "stage": "pair_cleanup",
                "reasons": reasons,
            }
        else:
            kept.append(row)
    parents = {r["id"]: r for r in kept if r["role"] == "machine"}
    noops = []
    for row in kept:
        if row["role"] == "attack":
            parent = parents[row["adv_source_id"]]
            assert parent["source_id"] == row["source_id"]
            assert parent["split"] == row["split"]
            raw = row["raw_text_sha256"] == parent["raw_text_sha256"]
            window = row["scored_window_sha256"] == parent["scored_window_sha256"]
            if raw or window:
                noops.append(
                    {
                        "id": row["id"],
                        "parent_id": parent["id"],
                        "raw_noop": raw,
                        "window_noop": window,
                    }
                )
    for value in rejected.values():
        value["primary_reason"] = value["reasons"][0]

    def order(r):
        return r["source_id"], r.get("role", ""), r.get("attack", ""), r["id"]

    return (
        sorted(kept, key=order),
        sorted(rejected.values(), key=order),
        collisions,
        sorted(noops, key=lambda r: r["id"]),
    )
