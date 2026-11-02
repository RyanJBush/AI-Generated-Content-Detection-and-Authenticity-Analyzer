"""Development-only R1-F execution, durable journal and one-way freeze assembly."""

import builtins
import contextlib
import datetime
import io
import os
import socket
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

from litmus import config
from litmus.data_prep.acquisition import file_hash
from litmus.data_prep.keys import canonical
from litmus.data_prep.manifest import validate_manifest
from litmus.data_prep.text import assess
from litmus.data_prep.verification import verify_source_version
from litmus.offline import offline_guards
from litmus.scorer.calibration import (
    CalibrationError,
    create_artifact,
    envelope,
    require,
    sha,
    strict_json,
    validate_artifact,
    validate_config,
    validate_freeze,
    validate_score_statistics,
)

MANIFEST = "8f0a36e95e9745e27bd444b94fe96381c5c0cd98744b2abd52bd2a6ce579c5d9"
DEV = "57bbfc53c6fc9bf482367d18aec29a1e991792fad75d9885e2ad4630ee467453"
RECONCILIATION = "836baccb57a834bca3c3fcd9e28862c1dbcf99879f6a22b008d3afc867d5a851"
RECON_PATH = "eval/results/r1e_budget_fix_source_reconciliation.json"
GPU = "NVIDIA GeForce RTX 4060 Laptop GPU"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read_json(path):
    return strict_json(path.read_text(encoding="utf-8"))


def new_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def new_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.PIPE
    )


def code_snapshot(repo):
    from litmus.scorer.identity import SOURCE_FILES

    paths = sorted(
        set(SOURCE_FILES)
        | {
            "scripts/calibrate_r1f.py",
            "src/litmus/offline.py",
            "src/litmus/report.py",
            "src/litmus/cli.py",
            "src/litmus/schemas.py",
        }
    )
    commit = git(repo, "rev-parse", "HEAD").decode().strip()
    require(
        not git(
            repo,
            "diff",
            "HEAD",
            "--",
            "src",
            "scripts",
            "tests",
            "pyproject.toml",
            "requirements.lock",
        ).strip(),
        "implementation_tree_not_clean",
    )
    require(
        not git(
            repo,
            "ls-files",
            "--others",
            "--exclude-standard",
            "src",
            "scripts",
            "tests",
        ).strip(),
        "uncommitted_implementation",
    )
    for path in paths:
        require(
            git(repo, "show", commit + ":" + path) == (repo / path).read_bytes(),
            "implementation_not_committed:" + path,
        )
    return {
        "implementation_commit": commit,
        "source_files_sha256": {p: file_hash(repo / p) for p in paths},
    }


def dev_projection(rows):
    require(len({r["id"] for r in rows}) == len(rows), "duplicate_input_id")
    require(all(r["split"] in ("dev", "test") for r in rows), "unknown_input_split")
    dev = [r for r in rows if r["split"] == "dev"]
    require(bool(dev), "no_development_rows")
    return dev, b"".join(canonical(r) + b"\n" for r in dev)


def load_dev(repo):
    manifest, _, retained = validate_manifest(repo / "eval/manifests/r1e/primary")
    require(
        manifest["manifest_sha256"] == MANIFEST, "prepared_manifest_identity_mismatch"
    )
    recon = repo / RECON_PATH
    require(file_hash(recon) == RECONCILIATION, "reconciliation_identity_mismatch")
    source_version = verify_source_version(repo, manifest, recon)
    rows, data = dev_projection(retained)
    require(
        sha(data) == DEV == manifest["payload"]["split_sha256"]["dev"],
        "dev_projection_mismatch",
    )
    require(
        len(rows) == 1484
        and Counter(r["role"] for r in rows)
        == {"human": 298, "machine": 298, "attack": 888},
        "dev_population_mismatch",
    )
    return rows, data, source_version


@contextlib.contextmanager
def scoring_guards(repo, rows):
    allowed = {
        (repo / "data/raid/prepared/primary" / r["text_blob"]).resolve() for r in rows
    }
    require(all(r["split"] == "dev" for r in rows), "test_row_in_scoring_guard")
    data_root = (repo / "data").resolve()
    saved = (builtins.open, io.open, os.open)
    names = ("connect", "connect_ex", "sendto")
    sockets = {n: getattr(socket.socket, n) for n in names}
    lookups = {
        n: getattr(socket, n)
        for n in ("getaddrinfo", "gethostbyname", "gethostbyname_ex")
    }
    attempts = {"connections": 0, "forbidden_data_access": 0}

    def checked(original):
        def call(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)):
                resolved = Path(os.fsdecode(path)).resolve()
                if resolved.is_relative_to(data_root) and resolved not in allowed:
                    attempts["forbidden_data_access"] += 1
                    raise CalibrationError("nondev_data_access_forbidden")
            return original(path, *args, **kwargs)

        return call

    def blocked(*args, **kwargs):
        attempts["connections"] += 1
        raise CalibrationError("network_forbidden")

    try:
        with offline_guards():
            builtins.open, io.open, os.open = tuple(checked(f) for f in saved)
            for n in names:
                setattr(socket.socket, n, blocked)
            for n in lookups:
                setattr(socket, n, blocked)
            yield attempts
    finally:
        builtins.open, io.open, os.open = saved
        for n, value in sockets.items():
            setattr(socket.socket, n, value)
        for n, value in lookups.items():
            setattr(socket, n, value)


def check_assets(repo):
    manifest = read_json(repo / "models.manifest.json")
    expected = {
        config.OBSERVER_DIR: (config.OBSERVER_REPO, config.OBSERVER_COMMIT),
        config.PERFORMER_DIR: (config.PERFORMER_REPO, config.PERFORMER_COMMIT),
    }
    for name, (model, revision) in expected.items():
        item = manifest[name]
        require(
            item["repo_id"] == model and item["revision"] == revision,
            "model_pin_mismatch",
        )
        for rel, identity in item["files"].items():
            path = (repo / "models" / name / rel).resolve()
            require(
                path.is_relative_to((repo / "models" / name).resolve())
                and path.is_file(),
                "local_model_asset_missing",
            )
            require(
                path.stat().st_size == identity["size"]
                and file_hash(path) == identity["sha256"],
                "local_model_asset_identity_mismatch:" + rel,
            )
    return file_hash(repo / "models.manifest.json")


@contextlib.contextmanager
def production_session(repo, rows):
    from litmus.scorer.analyzer import BinocularsAnalyzer
    from litmus.scorer.identity import (
        SOURCE_FILES,
        config_fields,
        scoring_config_hash,
        source_sha256,
        static_fields,
    )
    from litmus.scorer.loader import load_pair, profile_failures, read_profile

    require("torch" not in sys.modules, "fresh_scoring_process_required")
    started = time.monotonic()
    with scoring_guards(repo, rows) as attempts:
        assets = check_assets(repo)
        pair = load_pair(repo / "models", device="cuda")
        import torch

        require(
            not profile_failures(
                pair.profile,
                models=(("observer", pair.observer), ("performer", pair.performer)),
            ),
            "execution_profile_incomplete",
        )
        require(
            pair.profile["device_type"] == "cuda"
            and pair.profile["gpu_name"] == GPU
            and pair.profile["deterministic_algorithms"] is True,
            "primary_profile_required",
        )
        require(
            all(
                next(m.parameters()).device.type == "cuda" and not m.training
                for m in (pair.observer, pair.performer)
            ),
            "models_not_cuda_eval",
        )
        fields = config_fields(
            pair.profile,
            static_fields(pair.tokenizer_json_sha256),
            list(SOURCE_FILES),
            source_sha256(),
        )
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        session = {
            "pair": pair,
            "analyzer": BinocularsAnalyzer(),
            "fields": fields,
            "scoring_config_hash": scoring_config_hash(fields),
            "profile": pair.profile,
            "models_manifest_sha256": assets,
            "guards": attempts,
        }
        yield session
        require(
            read_profile(torch, pair.device, pair.observer, pair.performer)
            == pair.profile,
            "execution_profile_changed",
        )
        torch.cuda.synchronize()
        session["telemetry"] = {
            "elapsed_seconds": time.monotonic() - started,
            "peak_gpu_allocated": torch.cuda.max_memory_allocated(),
            "peak_gpu_reserved": torch.cuda.max_memory_reserved(),
        }
        require(not any(attempts.values()), "guard_attempts_detected")


def session_header(session, snapshot, run_id):
    return {
        "schema_version": "r1f-dev-run-v1",
        "run_id": run_id,
        "created": now(),
        "scoring_config": session["fields"],
        "scoring_config_hash": session["scoring_config_hash"],
        "models_manifest_sha256": session["models_manifest_sha256"],
        "prepared_manifest_sha256": MANIFEST,
        "dev_set_id": DEV,
        "reconciliation_sha256": RECONCILIATION,
        **snapshot,
    }


def read_dev_text(repo, row, inputs):
    require(
        row["split"] == "dev" and any(row == item for item in inputs),
        "nondev_or_unknown_row",
    )
    base = (repo / "data/raid/prepared/primary").resolve()
    path = (base / row["text_blob"]).resolve()
    require(path.is_relative_to(base / "texts"), "blob_path_escape")
    data = path.read_bytes()
    require(sha(data) == row["raw_text_sha256"], "raw_blob_hash_mismatch")
    return data.decode("utf-8", errors="strict")


def score_row(repo, row, rows, session):
    text = read_dev_text(repo, row, rows)
    observed, errors = assess(text, session["pair"].tokenizer)
    require(
        not errors and all(row.get(k) == v for k, v in observed.items()),
        "prepared_window_mismatch",
    )
    ev = session["analyzer"].score_text(session["pair"], text, apply_calibration=False)
    require(
        ev.details.get("scoring_config_hash") == session["scoring_config_hash"]
        and ev.details.get("scoring_config") == session["fields"]
        and ev.details.get("execution_profile_complete") is True
        and not ev.details.get("execution_profile_failures"),
        "scoring_identity_or_profile_failure",
    )
    require(
        ev.raw_score is not None
        and ev.result.value == "inconclusive"
        and ev.reasons == ["calibration_disabled_for_creation"],
        "numerical_or_scoring_failure",
    )
    stats = {
        k: ev.details[k]
        for k in ("nll_performer", "xent", "n_input_tokens", "n_target_tokens")
    }
    stats["score"] = ev.raw_score
    validate_score_statistics(stats)
    require(
        ev.details["scored_window"]
        == {
            k: row[k]
            for k in ("tokens_total", "tokens_scored", "truncated", "scored_char_range")
        },
        "scored_window_mismatch",
    )
    return {
        "id": row["id"],
        "source_id": row["source_id"],
        "split": "dev",
        "role": row["role"],
        "attack": row["attack"],
        "raw_text_sha256": row["raw_text_sha256"],
        "scored_window_sha256": row["scored_window_sha256"],
        "scoring_config_hash": session["scoring_config_hash"],
        "status": "valid",
        "stats": stats,
        "scored_window": ev.details["scored_window"],
        "reasons": [],
    }


@contextlib.contextmanager
def writer_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "writer.lock"
    token = {"pid": os.getpid(), "token": uuid.uuid4().hex, "created": now()}
    try:
        new_json(path, token)
    except FileExistsError as error:
        raise CalibrationError(
            "writer_lock_exists; stale locks require inspection"
        ) from error
    try:
        yield
    finally:
        require(read_json(path) == token, "writer_lock_owner_changed")
        path.unlink()


def append_event(path, event):
    with path.open("ab") as stream:
        stream.write(canonical(event) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def journal_state(path, rows, header):
    inputs = {r["id"]: r for r in rows}
    done, pending = {}, None
    if not path.exists():
        return done, pending
    data = path.read_bytes()
    require(
        not data or data.endswith(b"\n"),
        "journal_truncated_tail; explicit recovery required",
    )
    for line in data.splitlines():
        event = strict_json(line)
        require(
            set(event) == {"event", "id", "data"} and event["id"] in inputs,
            "journal_unknown_row",
        )
        rid = event["id"]
        require(rid not in done, "duplicate_completed_row")
        expected_id = rows[len(done)]["id"]
        require(rid == expected_id, "journal_order_or_gap")
        if event["event"] == "attempt":
            require(
                pending in (None, rid)
                and event["data"] == header["scoring_config_hash"],
                "journal_attempt",
            )
            pending = rid
        else:
            require(
                event["event"] == "completion" and pending == rid,
                "journal_completion_without_attempt",
            )
            result = event["data"]
            validate_row(result, inputs[rid], header)
            done[rid], pending = result, None
    return done, pending


def validate_row(result, row, header):
    base = {
        "id",
        "source_id",
        "split",
        "role",
        "attack",
        "raw_text_sha256",
        "scored_window_sha256",
        "scoring_config_hash",
        "status",
        "stats",
        "scored_window",
        "reasons",
    }
    require(isinstance(result, dict) and set(result) == base, "score_ledger_field_set")
    for key in (
        "id",
        "source_id",
        "split",
        "role",
        "attack",
        "raw_text_sha256",
        "scored_window_sha256",
    ):
        require(result[key] == row[key], "score_row_identity_mismatch:" + key)
    require(
        result["split"] == "dev"
        and result["scoring_config_hash"] == header["scoring_config_hash"],
        "score_hash_or_split_mismatch",
    )
    if result["status"] == "valid":
        validate_score_statistics(result["stats"])
        require(
            result["reasons"] == []
            and result["scored_window"]
            == {
                k: row[k]
                for k in (
                    "tokens_total",
                    "tokens_scored",
                    "truncated",
                    "scored_char_range",
                )
            },
            "score_window_mismatch",
        )
        require(
            result["stats"]["n_input_tokens"] == row["tokens_scored"],
            "score_count_mismatch",
        )
    else:
        require(
            result["status"] == "failed"
            and result["stats"] is None
            and result["scored_window"] is None
            and isinstance(result["reasons"], list)
            and len(result["reasons"]) == 1
            and isinstance(result["reasons"][0], str),
            "invalid_failure_row",
        )


def run_rows(directory, rows, projection, header, scorer):
    validate_config(header["scoring_config"], header["scoring_config_hash"])
    with writer_lock(directory):
        header_path = directory / "header.json"
        if header_path.exists():
            old = read_json(header_path)
            require(
                {k: v for k, v in old.items() if k != "created"}
                == {k: v for k, v in header.items() if k != "created"},
                "resume_header_mismatch",
            )
            header = old
            if not (directory / "dev_input.jsonl").exists():
                require(
                    not (directory / "journal.jsonl").exists(),
                    "missing_input_after_journal_started",
                )
                new_bytes(directory / "dev_input.jsonl", projection)
            require(
                (directory / "dev_input.jsonl").read_bytes() == projection,
                "resume_dev_input_mismatch",
            )
        else:
            require(
                not (directory / "journal.jsonl").exists(), "journal_without_header"
            )
            new_json(header_path, header)
            new_bytes(directory / "dev_input.jsonl", projection)
        journal = directory / "journal.jsonl"
        done, _ = journal_state(journal, rows, header)
        require(
            not any(v["status"] == "failed" for v in done.values()),
            "terminal_failure_requires_review",
        )
        for row in rows[len(done) :]:
            append_event(
                journal,
                {
                    "event": "attempt",
                    "id": row["id"],
                    "data": header["scoring_config_hash"],
                },
            )
            try:
                result = scorer(row)
                validate_row(result, row, header)
            except Exception as error:
                failure = {
                    k: row[k]
                    for k in (
                        "id",
                        "source_id",
                        "split",
                        "role",
                        "attack",
                        "raw_text_sha256",
                        "scored_window_sha256",
                    )
                }
                failure.update(
                    scoring_config_hash=header["scoring_config_hash"],
                    status="failed",
                    stats=None,
                    scored_window=None,
                    reasons=[type(error).__name__ + ":" + str(error)],
                )
                append_event(
                    journal, {"event": "completion", "id": row["id"], "data": failure}
                )
                raise
            append_event(
                journal, {"event": "completion", "id": row["id"], "data": result}
            )
            done[row["id"]] = result
            if len(done) % 50 == 0:
                print(f"Completed {len(done)}/{len(rows)} development rows", flush=True)
        ordered = [done[r["id"]] for r in rows]
        score_bytes = b"".join(canonical(r) + b"\n" for r in ordered)
        if (directory / "scores.jsonl").exists():
            require(
                (directory / "scores.jsonl").read_bytes() == score_bytes,
                "final_ledger_mismatch",
            )
        else:
            new_bytes(directory / "scores.jsonl", score_bytes)
        return ordered


def recover_tail(directory, rows, header):
    with writer_lock(directory):
        path = directory / "journal.jsonl"
        original = path.read_bytes()
        require(original and not original.endswith(b"\n"), "no_truncated_tail")
        prefix, _, tail = original.rpartition(b"\n")
        prefix = prefix + b"\n" if prefix else b""
        backup = directory / ("journal.damaged." + sha(original) + ".jsonl")
        probe = directory / ("journal.validated." + sha(prefix) + ".jsonl")
        new_bytes(backup, original)
        new_bytes(probe, prefix)
        journal_state(
            probe, rows, header
        )  # rejects earlier corruption before replacing
        temporary = directory / "journal.recovered.tmp"
        new_bytes(temporary, prefix)
        temporary.replace(path)
        new_json(
            directory / ("recovery." + uuid.uuid4().hex + ".json"),
            {
                "backup_sha256": sha(original),
                "prefix_sha256": sha(prefix),
                "tail_sha256": sha(tail),
                "reason": "explicit inspected truncated-tail recovery",
                "created": now(),
            },
        )


def verify_dev(directory, rows, projection):
    header = read_json(directory / "header.json")
    validate_config(header["scoring_config"], header["scoring_config_hash"])
    require(
        (directory / "dev_input.jsonl").read_bytes() == projection
        and sha(projection) == header["dev_set_id"],
        "verification_dev_projection",
    )
    done, pending = journal_state(directory / "journal.jsonl", rows, header)
    require(pending is None and len(done) == len(rows), "incomplete_development_run")
    ordered = [done[r["id"]] for r in rows]
    require(
        (directory / "scores.jsonl").read_bytes()
        == b"".join(canonical(r) + b"\n" for r in ordered),
        "final_score_ledger_mismatch",
    )
    negatives = [
        r["stats"]["score"]
        for r in ordered
        if r["role"] == "human" and r["status"] == "valid"
    ]
    failures = [r for r in ordered if r["status"] == "failed"]
    counts = {
        "input_rows": len(rows),
        "valid_rows": len(rows) - len(failures),
        "failed_rows": len(failures),
        "eligible_development_negatives": len(negatives),
        "input_roles": dict(Counter(r["role"] for r in rows)),
        "failures_by_role": dict(Counter(r["role"] for r in failures)),
    }
    bindings = {
        k: header[k]
        for k in ("dev_set_id", "prepared_manifest_sha256", "reconciliation_sha256")
    }
    bindings.update(
        scores_sha256=file_hash(directory / "scores.jsonl"),
        source_run_id=header["run_id"],
        failed_negatives=sum(r["role"] == "human" for r in failures),
    )
    artifact = create_artifact(
        negatives, header["scoring_config"], bindings, header["created"]
    )
    return header, ordered, failures, counts, artifact


def lexicon_identity(repo):
    from litmus.quality.lexicon import LEXICON_NAMES, load_lexicon

    lexicons = {
        n: {"version": load_lexicon(n).version, "sha256": load_lexicon(n).sha256}
        for n in LEXICON_NAMES
    }
    sources = {
        p.relative_to(repo).as_posix(): file_hash(p)
        for p in sorted((repo / "src/litmus/quality").glob("*.py"))
    }
    return lexicons, sources


def assemble_freeze(
    repo, directory, artifact, artifact_bytes, failures_bytes, evidence_paths
):
    header = read_json(directory / "header.json")
    a = validate_artifact(artifact)
    require(strict_json(artifact_bytes) == artifact, "artifact_bytes_mismatch")
    lexicons, quality_sources = lexicon_identity(repo)
    payload = {
        k: a[k]
        for k in (
            "scoring_config_hash",
            "scoring_config",
            "threshold_c",
            "comparison",
            "score_direction",
            "n_dev_negatives",
            "prepared_manifest_sha256",
            "dev_set_id",
            "reconciliation_sha256",
            "scores_sha256",
        )
    }
    payload.update(
        schema_version="r1f-freeze-v1",
        calibration_file_sha256=sha(artifact_bytes),
        calibration_artifact_sha256=artifact["artifact_sha256"],
        one_percent_enabled=False,
        implementation_commit=header["implementation_commit"],
        source_files_sha256=header["source_files_sha256"],
        failures_sha256=sha(failures_bytes),
        dev_input_sha256=file_hash(directory / "dev_input.jsonl"),
        lexicons=lexicons,
        quality_sources_sha256=quality_sources,
        evidence_sha256={
            p.relative_to(repo).as_posix(): file_hash(p) for p in evidence_paths
        },
        historical_transfer_compliance_proven=False,
    )
    freeze = envelope(payload, "freeze_sha256")
    validate_freeze(freeze, artifact)
    require(
        payload["calibration_file_sha256"] == sha(artifact_bytes),
        "artifact_file_mismatch",
    )
    return freeze


def verify_committed(repo, paths, commit="HEAD"):
    for path in paths:
        relative = path.relative_to(repo).as_posix()
        require(
            git(repo, "show", commit + ":" + relative) == path.read_bytes(),
            "uncommitted_or_tampered_artifact:" + relative,
        )
    return git(repo, "rev-parse", commit).decode().strip()


def synthetic_result(repo, session, text):
    ev = session["analyzer"].score_text(session["pair"], text, apply_calibration=False)
    require(
        ev.raw_score is not None
        and ev.reasons == ["calibration_disabled_for_creation"]
        and ev.details.get("execution_profile_complete") is True
        and ev.details.get("scoring_config_hash") == session["scoring_config_hash"],
        "synthetic_score_failure",
    )
    stats = {
        k: ev.details[k]
        for k in ("nll_performer", "xent", "n_input_tokens", "n_target_tokens")
    }
    stats["score"] = ev.raw_score
    validate_score_statistics(stats)
    return {"stats": stats, "scored_window": ev.details["scored_window"]}


def receipt_scientific(receipt):
    return {
        k: receipt[k]
        for k in (
            "snapshot",
            "scoring_config",
            "scoring_config_hash",
            "models_manifest_sha256",
            "synthetic_input_sha256",
            "synthetic_result",
        )
    }


def check_preflights(paths, header=None):
    receipts = [read_json(p) for p in paths]
    require(
        len(receipts) == 2
        and all(
            r["status"] == "PASS" and not any(r["guards"].values()) for r in receipts
        ),
        "preflight_receipt_invalid",
    )
    require(
        receipt_scientific(receipts[0]) == receipt_scientific(receipts[1]),
        "synthetic_reproducibility_failure",
    )
    if header is not None:
        for r in receipts:
            require(
                all(
                    r[k] == header[k]
                    for k in (
                        "scoring_config",
                        "scoring_config_hash",
                        "models_manifest_sha256",
                    )
                )
                and r["snapshot"]["source_files_sha256"]
                == header["source_files_sha256"]
                and r["snapshot"]["implementation_commit"]
                == header["implementation_commit"],
                "preflight_session_mismatch",
            )
    return receipts


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "preflight",
            "score-dev",
            "audit-dev",
            "verify-dev",
            "freeze",
            "verify-freeze",
            "recover-tail",
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--run-dir", type=Path, default=Path("eval/results/r1f/primary")
    )
    parser.add_argument(
        "--preflight-a", type=Path, default=Path("eval/results/r1f/preflight_a.json")
    )
    parser.add_argument(
        "--preflight-b", type=Path, default=Path("eval/results/r1f/preflight_b.json")
    )
    parser.add_argument(
        "--audit", type=Path, default=Path("eval/results/r1f/dev_repeat_audit.json")
    )
    parser.add_argument(
        "--checks",
        type=Path,
        default=Path("eval/results/r1f_implementation_verification.json"),
    )
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    directory = (repo / args.run_dir).resolve()
    require(
        directory.is_relative_to((repo / "eval/results/r1f").resolve()),
        "run_directory_out_of_scope",
    )
    for name in ("output", "preflight_a", "preflight_b", "audit", "checks", "artifact"):
        value = getattr(args, name)
        if value is not None:
            value = (repo / value).resolve()
            require(
                value.is_relative_to(repo) and not value.is_relative_to(repo / "data"),
                "output_or_evidence_path_out_of_scope",
            )
            setattr(args, name, value)
    if args.output is not None:
        require(not args.output.exists(), "output_already_exists")
    snapshot = code_snapshot(repo)
    rows, projection, source_version = load_dev(repo)
    started = time.monotonic()
    cpu_started = time.process_time()
    if args.operation == "preflight":
        require(args.output is not None, "output_required")
        synthetic_path = repo / "eval/inputs/r1b2/len512_00.txt"
        synthetic = synthetic_path.read_bytes()
        require(
            synthetic
            == git(
                repo,
                "show",
                snapshot["implementation_commit"] + ":eval/inputs/r1b2/len512_00.txt",
            ),
            "synthetic_input_not_committed",
        )
        print("Verifying pinned local assets and loading CUDA pair", flush=True)
        with production_session(repo, rows) as session:
            result = synthetic_result(repo, session, synthetic.decode("utf-8"))
        receipt = {
            "status": "PASS",
            "snapshot": snapshot,
            "scoring_config": session["fields"],
            "scoring_config_hash": session["scoring_config_hash"],
            "models_manifest_sha256": session["models_manifest_sha256"],
            "synthetic_input_sha256": sha(synthetic),
            "synthetic_result": result,
            "guards": session["guards"],
            "telemetry": session["telemetry"],
            "created": now(),
            "source_version": source_version,
        }
        new_json(args.output, receipt)
        print(
            "Preflight PASS; scoring_config_hash=" + session["scoring_config_hash"],
            flush=True,
        )
        return
    if args.operation in ("score-dev", "audit-dev"):
        check_preflights((args.preflight_a, args.preflight_b))
        with production_session(repo, rows) as session:
            header = session_header(session, snapshot, directory.name)
            check_preflights((args.preflight_a, args.preflight_b), header)
            if args.operation == "score-dev":
                results = run_rows(
                    directory,
                    rows,
                    projection,
                    header,
                    lambda row: score_row(repo, row, rows, session),
                )
            else:
                require(args.output is not None, "output_required")
                original, original_rows, _, _, _ = verify_dev(
                    directory, rows, projection
                )
                require(
                    all(original[k] == header[k] for k in header if k != "created"),
                    "audit_session_mismatch",
                )
                selected = [r for r in rows if r["role"] == "human"][:10]
                originals = {r["id"]: r for r in original_rows}
                results = [score_row(repo, row, rows, session) for row in selected]
                require(
                    all(r == originals[r["id"]] for r in results),
                    "dev_reproducibility_failure",
                )
        receipt = {
            "status": "PASS",
            "operation": args.operation,
            "scoring_config_hash": session["scoring_config_hash"],
            "source_files_sha256": snapshot["source_files_sha256"],
            "implementation_commit": snapshot["implementation_commit"],
            "rows": len(results),
            "guards": session["guards"],
            "telemetry": session["telemetry"],
            "elapsed_seconds": time.monotonic() - started,
            "cpu_seconds": time.process_time() - cpu_started,
            "scores_sha256": file_hash(directory / "scores.jsonl"),
            "source_version": source_version,
        }
        if args.operation == "audit-dev":
            receipt["repeated_rows"] = results
            new_json(args.output, receipt)
        else:
            destination = directory / "execution.json"
            if destination.exists():
                destination = directory / (
                    "resume_execution." + uuid.uuid4().hex + ".json"
                )
            new_json(destination, receipt)
        print(args.operation + " PASS", flush=True)
        return
    if args.operation == "recover-tail":
        header = read_json(directory / "header.json")
        require(
            header["source_files_sha256"] == snapshot["source_files_sha256"],
            "recovery_source_mismatch",
        )
        recover_tail(directory, rows, header)
        print("Truncated tail preserved and recovered; no scoring", flush=True)
        return
    header, scored, failures, counts, artifact = verify_dev(directory, rows, projection)
    require(
        header["source_files_sha256"] == snapshot["source_files_sha256"],
        "verification_source_mismatch",
    )
    check_preflights((args.preflight_a, args.preflight_b), header)
    if args.operation == "verify-dev":
        require(args.output is not None, "output_required")
        new_json(
            args.output,
            {
                "status": "PASS",
                "counts": counts,
                "artifact_sha256": artifact["artifact_sha256"],
                "source_version": source_version,
                "scoring_config_hash": header["scoring_config_hash"],
            },
        )
        print("Development ledger verification PASS", flush=True)
        return
    audit = read_json(args.audit)
    execution = read_json(directory / "execution.json")
    for receipt in (audit, execution):
        require(
            receipt["status"] == "PASS"
            and not any(receipt["guards"].values())
            and receipt["scoring_config_hash"] == header["scoring_config_hash"]
            and receipt["source_files_sha256"] == header["source_files_sha256"]
            and receipt["implementation_commit"] == header["implementation_commit"]
            and receipt["scores_sha256"] == file_hash(directory / "scores.jsonl"),
            "execution_or_audit_mismatch",
        )
    first_humans = [r["id"] for r in rows if r["role"] == "human"][:10]
    require(
        [r["id"] for r in audit["repeated_rows"]] == first_humans, "audit_wrong_rows"
    )
    scored_map = {r["id"]: r for r in scored}
    require(
        all(row == scored_map[row["id"]] for row in audit["repeated_rows"]),
        "audit_score_mismatch",
    )
    require(
        execution["rows"] == len(rows) and audit["rows"] == 10,
        "execution_count_mismatch",
    )
    require(read_json(args.checks)["status"] == "PASS", "implementation_checks_missing")
    artifact_bytes = canonical(artifact) + b"\n"
    negative_raw = [
        r["stats"]["score"]
        for r in scored
        if r["role"] == "human" and r["status"] == "valid"
    ]
    bindings = {
        k: artifact["payload"][k]
        for k in (
            "dev_set_id",
            "prepared_manifest_sha256",
            "reconciliation_sha256",
            "scores_sha256",
            "source_run_id",
            "failed_negatives",
        )
    }
    independent = create_artifact(
        list(reversed(negative_raw)),
        header["scoring_config"],
        bindings,
        header["created"],
    )
    require(
        canonical(independent) + b"\n" == artifact_bytes, "artifact_reassembly_mismatch"
    )
    failures_bytes = b"".join(canonical(r) + b"\n" for r in failures)
    artifact_path = args.artifact or repo / "calibrations" / (
        "r1f_" + header["scoring_config_hash"] + "_alpha005.json"
    )
    evidence_paths = [
        args.preflight_a,
        args.preflight_b,
        args.audit,
        args.checks,
        directory / "execution.json",
        directory / "verification.json",
    ]
    if args.operation == "freeze":
        require(
            args.output is not None and not artifact_path.exists(),
            "fresh_freeze_and_artifact_paths_required",
        )
        with writer_lock(directory):
            new_bytes(directory / "failures.jsonl", failures_bytes)
            new_json(directory / "counts.json", counts)
            new_json(
                directory / "verification.json",
                {
                    "status": "PASS",
                    "counts": counts,
                    "scoring_config_hash": header["scoring_config_hash"],
                    "artifact_sha256": artifact["artifact_sha256"],
                    "artifact_file_sha256": sha(artifact_bytes),
                    "independent_reassembly": "byte-identical",
                    "empirical_dev_fpr": artifact["payload"]["above"]
                    / len(negative_raw),
                    "test_scoring_performed": False,
                    "historical_transfer_compliance_proven": False,
                    "source_version": source_version,
                },
            )
            freeze = assemble_freeze(
                repo,
                directory,
                artifact,
                artifact_bytes,
                failures_bytes,
                evidence_paths,
            )
            new_bytes(artifact_path, artifact_bytes)
            new_json(args.output, freeze)
        print(
            "Freeze validated; commit and independent review still required",
            flush=True,
        )
    else:
        freeze_path = repo / "eval/freezes/r1f_freeze.json"
        require(
            read_json(directory / "counts.json") == counts, "published_counts_mismatch"
        )
        require(
            artifact_path.read_bytes() == artifact_bytes
            and (directory / "failures.jsonl").read_bytes() == failures_bytes,
            "published_artifact_or_failures_mismatch",
        )
        expected = assemble_freeze(
            repo, directory, artifact, artifact_bytes, failures_bytes, evidence_paths
        )
        require(read_json(freeze_path) == expected, "freeze_reassembly_mismatch")
        paths = [
            freeze_path,
            artifact_path,
            directory / "scores.jsonl",
            directory / "header.json",
            directory / "dev_input.jsonl",
            directory / "failures.jsonl",
            directory / "counts.json",
            *evidence_paths,
        ]
        commit = verify_committed(repo, paths)
        print("Committed freeze validation PASS at " + commit, flush=True)
