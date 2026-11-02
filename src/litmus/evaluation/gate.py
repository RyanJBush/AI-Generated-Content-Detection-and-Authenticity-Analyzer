"""Accepted identity gates and logged, single-read held-out access."""

import builtins
import contextlib
import io
import os
import socket
from collections import Counter
from pathlib import Path

from litmus.calibration_run import git, read_json
from litmus.data_prep.acquisition import file_hash
from litmus.data_prep.keys import canonical
from litmus.data_prep.manifest import validate_manifest
from litmus.data_prep.verification import verify_source_version
from litmus.evaluation.metrics import POLICY
from litmus.offline import offline_guards
from litmus.scorer.calibration import (
    CalibrationError,
    require,
    sha,
    validate_artifact,
    validate_freeze,
)

ACCEPTED = "bf455659053cca15ec82cb85065613c6b7459a44"
CFG = "10f0fa316fa5f3d87c7819f86f09ecedc5bc5b1b71e9250d8586aece7390db2f"
TEST = "af6959b6ff803b9e60ea2408e6a0305577f1641c10f884429991f84332c30348"
MANIFEST = "8f0a36e95e9745e27bd444b94fe96381c5c0cd98744b2abd52bd2a6ce579c5d9"
FREEZE = "eval/freezes/r1f_freeze.json"
ARTIFACT = f"calibrations/r1f_{CFG}_alpha005.json"
RECON = "eval/results/r1e_budget_fix_source_reconciliation.json"
POLICY_PATH = "eval/policies/r1g_policy.json"
G_FILES = [
    "src/litmus/evaluation/" + n + ".py"
    for n in ("__init__", "gate", "journal", "metrics", "run")
] + ["scripts/evaluate_r1g.py", POLICY_PATH]


def check_hashes(repo, mapping):
    for rel, expected in mapping.items():
        require(file_hash(repo / rel) == expected, "source_or_evidence_changed:" + rel)


def test_projection(retained):
    require(len({r["id"] for r in retained}) == len(retained), "duplicate_retained_id")
    require(all(r["split"] in ("dev", "test") for r in retained), "unknown_split")
    rows = [r for r in retained if r["split"] == "test"]
    require(bool(rows), "no_test_rows")
    return rows, b"".join(canonical(r) + b"\n" for r in rows)


def accepted_state(repo):
    # Compare all historical E/F receipts and scientific metadata to accepted Git blobs.
    historical = (
        git(repo, "ls-tree", "-r", "--name-only", ACCEPTED).decode().splitlines()
    )
    paths = [
        p
        for p in historical
        if p.startswith(
            (
                "calibrations/",
                "eval/freezes/",
                "eval/results/r1f",
                "eval/manifests/r1e/",
                "eval/results/r1e_",
            )
        )
    ]
    require(len(paths) == 48, "accepted_evidence_inventory")
    for path in paths:
        require(
            (repo / path).read_bytes() == git(repo, "show", ACCEPTED + ":" + path),
            "accepted_blob_changed:" + path,
        )
    freeze, artifact = read_json(repo / FREEZE), read_json(repo / ARTIFACT)
    validate_freeze(freeze, artifact)
    calibration = validate_artifact(artifact)
    f = freeze["payload"]
    require(
        file_hash(repo / FREEZE)
        == "2b052f43f4f8b487968a1f1e7815630c1ea6fb1e523d2957239b21afe1156ba7",
        "freeze_file",
    )
    require(
        file_hash(repo / ARTIFACT)
        == "edd84087ab56d25d43df653cdaaaa2f06dccdb196108c32c67c9e1a505822134",
        "artifact_file",
    )
    require(
        f["scoring_config_hash"] == CFG and f["threshold_c"] == POLICY["threshold_c"],
        "fixed_configuration",
    )
    require(f["historical_transfer_compliance_proven"] is False, "historical_exception")
    manifest, _, retained = validate_manifest(repo / "eval/manifests/r1e/primary")
    require(manifest["manifest_sha256"] == MANIFEST, "prepared_manifest")
    require(file_hash(repo / RECON) == f["reconciliation_sha256"], "reconciliation")
    reconciliation = verify_source_version(repo, manifest, repo / RECON)
    require(
        reconciliation["mode"] == "explicit_historical_source_reconciliation",
        "source_reconciliation_required",
    )
    rows, projection = test_projection(retained)
    require(
        sha(projection) == TEST == manifest["payload"]["split_sha256"]["test"],
        "test_projection",
    )
    require(
        len(rows) == 3361 and len({r["source_id"] for r in rows}) == 675,
        "test_population",
    )
    require(
        Counter(r["role"] for r in rows)
        == {"human": 675, "machine": 675, "attack": 2011},
        "test_roles",
    )
    require(
        Counter(r["attack"] for r in rows if r["role"] == "attack")
        == {"homoglyph": 675, "paraphrase": 661, "zero_width_space": 675},
        "test_attacks",
    )
    machines = {r["source_id"]: r for r in rows if r["role"] == "machine"}
    require(len(machines) == 675, "unique_machine_groups")
    for row in rows:
        require(row["source_id"] in machines, "missing_parent_group")
        if row["role"] == "attack":
            require(
                row["adv_source_id"] == machines[row["source_id"]]["id"], "parent_link"
            )
    require(
        len({r["domain"] for r in machines.values()}) == 8
        and len({r["model"] for r in machines.values()}) == 11,
        "slice_dimensions",
    )
    from litmus.evaluation.metrics import slices

    clean_slices, pair_slices = slices(rows)
    require(len(clean_slices) == 112 and len(pair_slices) == 20, "slice_inventory")
    mapping = {
        **f["source_files_sha256"],
        **f["quality_sources_sha256"],
        **read_json(repo / RECON)["verification_source_sha256"],
    }
    mapping.update(
        {
            f"src/litmus/quality/lexicons/{name}.txt": v["sha256"]
            for name, v in f["lexicons"].items()
        }
    )
    mapping.update({p: file_hash(repo / p) for p in paths})
    check_hashes(repo, mapping)
    from litmus.scorer.identity import SOURCE_FILES, source_sha256

    require(
        list(SOURCE_FILES) == f["scoring_config"]["source_files"]
        and source_sha256() == f["scoring_config"]["source_sha256"],
        "scorer_source_identity",
    )
    return {
        "rows": rows,
        "projection": projection,
        "freeze": freeze,
        "artifact": artifact,
        "calibration": calibration,
        "hashes": mapping,
        "source_version": reconciliation,
    }


def evaluation_snapshot(repo):
    require(read_json(repo / POLICY_PATH) == POLICY, "policy_lock")
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
            POLICY_PATH,
        ).strip(),
        "uncommitted_implementation",
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
        "untracked_implementation",
    )
    for p in G_FILES:
        require(
            git(repo, "show", commit + ":" + p) == (repo / p).read_bytes(),
            "g_source_not_committed",
        )
    return {
        "evaluation_commit": commit,
        "evaluation_sources_sha256": {p: file_hash(repo / p) for p in G_FILES},
        "policy_sha256": sha(canonical(POLICY)),
    }


class Access:
    """One current durable-intent token; all other data opens are denied."""

    def __init__(self, repo, rows):
        self.repo, self.rows = repo, {r["id"]: r for r in rows}
        require(len(self.rows) == len(rows), "access_duplicate_id")
        self.allowed = {}
        for r in rows:
            require(r["split"] == "test", "non_test_access_population")
            path = (repo / "data/raid/prepared/primary" / r["text_blob"]).resolve()
            require(
                path.is_relative_to(
                    (repo / "data/raid/prepared/primary/texts").resolve()
                ),
                "blob_escape",
            )
            self.allowed[r["id"]] = path
        self.root = (repo / "data").resolve()
        self.token = None
        self.opens = self.blocked = 0

    def authorize(self, row, *, durable):
        require(
            durable and row == self.rows.get(row["id"]) and self.token is None,
            "unlogged_or_unknown_read",
        )
        self.token = self.allowed[row["id"]]

    def checked(self, original):
        def call(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)):
                resolved = Path(os.fsdecode(path)).resolve()
                if resolved.is_relative_to(self.root):
                    mode = args[0] if args else kwargs.get("mode", "r")
                    if resolved != self.token or mode not in ("rb", "r"):
                        self.blocked += 1
                        raise CalibrationError("unlogged_or_forbidden_data_access")
                    self.token = None
                    self.opens += 1
            return original(path, *args, **kwargs)

        return call

    def blocked_call(self, *args, **kwargs):
        self.blocked += 1
        raise CalibrationError("network_forbidden")

    def __enter__(self):
        self.offline = offline_guards()
        self.offline.__enter__()
        self.files = builtins.open, io.open, os.open
        builtins.open, io.open, os.open = tuple(self.checked(f) for f in self.files)
        self.sockets = {
            n: getattr(socket.socket, n) for n in ("connect", "connect_ex", "sendto")
        }
        self.lookups = {
            n: getattr(socket, n)
            for n in ("getaddrinfo", "gethostbyname", "gethostbyname_ex")
        }
        for n in self.sockets:
            setattr(socket.socket, n, self.blocked_call)
        for n in self.lookups:
            setattr(socket, n, self.blocked_call)
        return self

    def __exit__(self, *error):
        builtins.open, io.open, os.open = self.files
        for n, v in self.sockets.items():
            setattr(socket.socket, n, v)
        for n, v in self.lookups.items():
            setattr(socket, n, v)
        self.offline.__exit__(*error)


@contextlib.contextmanager
def session(repo, accepted, snapshot):
    import sys
    import time

    from litmus.calibration_run import check_assets
    from litmus.scorer.analyzer import BinocularsAnalyzer
    from litmus.scorer.identity import (
        SOURCE_FILES,
        config_fields,
        scoring_config_hash,
        source_sha256,
        static_fields,
    )
    from litmus.scorer.loader import load_pair, profile_failures, read_profile

    require("torch" not in sys.modules, "fresh_process_required")
    started = time.monotonic()
    with Access(repo, accepted["rows"]) as access:
        assets = check_assets(repo)
        require(
            assets
            == read_json(repo / "eval/results/r1f/preflight_a.json")[
                "models_manifest_sha256"
            ],
            "assets_manifest_identity",
        )
        pair = load_pair(repo / "models", device="cuda")
        import torch

        fields = config_fields(
            pair.profile,
            static_fields(pair.tokenizer_json_sha256),
            list(SOURCE_FILES),
            source_sha256(),
        )
        require(
            fields == accepted["calibration"]["scoring_config"]
            and scoring_config_hash(fields) == CFG,
            "exact_execution_profile",
        )
        require(
            not profile_failures(
                pair.profile,
                models=(("observer", pair.observer), ("performer", pair.performer)),
            ),
            "incomplete_profile",
        )
        analyzer = BinocularsAnalyzer(calibrations_dir=repo / "calibrations")
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()

        def check():
            check_hashes(
                repo, {**accepted["hashes"], **snapshot["evaluation_sources_sha256"]}
            )
            require(
                read_profile(torch, pair.device, pair.observer, pair.performer)
                == pair.profile,
                "execution_profile_changed",
            )
            require(
                all(
                    not m.training and next(m.parameters()).device.type == "cuda"
                    for m in (pair.observer, pair.performer)
                ),
                "model_state_changed",
            )
            require(access.blocked == 0, "guard_attempts_detected")

        value = {
            "pair": pair,
            "analyzer": analyzer,
            "fields": fields,
            "check": check,
            "access": access,
            "assets": assets,
        }
        check()
        yield value
        check()
        torch.cuda.synchronize()
        value["telemetry"] = {
            "elapsed_seconds": time.monotonic() - started,
            "peak_gpu_allocated": torch.cuda.max_memory_allocated(),
            "peak_gpu_reserved": torch.cuda.max_memory_reserved(),
            "actual_test_opens": access.opens,
            "blocked_operations": access.blocked,
        }
