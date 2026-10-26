"""Task 1 D11 drift probes through the production scorer (SPEC §3.1 D11 measurements).

Scores the fixed fixture texts with the pinned 0.5B pair under several weight-dtype/device
configurations, repeating each, and compares every run with the GPU fp32 reference.
"Dtype" is the model weight dtype only; log-softmax and reductions are float32 in litmus.binoculars.
Usage: .venv\\Scripts\\python.exe eval\\drift.py
"""
import argparse
import gc
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from litmus.binoculars import NumericalScoringError, binoculars_statistics  # noqa: E402
from litmus.config import MAX_LENGTH, MODEL_REVISIONS  # noqa: E402

OBSERVER = "Qwen/Qwen2.5-0.5B"
PERFORMER = "Qwen/Qwen2.5-0.5B-Instruct"
FIXTURE = ROOT / "eval" / "fixtures" / "drift_texts.json"
OUT_PATH = ROOT / "eval" / "results" / "runtime_drift.json"
STATS = ["nll_performer", "nll_observer", "xent", "score"]
CONFIGS = {
    "gpu_fp32": ("cuda", torch.float32),
    "gpu_bf16": ("cuda", torch.bfloat16),
    "gpu_fp16": ("cuda", torch.float16),
    "cpu_fp32": ("cpu", torch.float32),
}
REFERENCE = ("gpu_fp32", 0)
SOURCE_FILES = ["eval/drift.py", "src/litmus/binoculars.py", "src/litmus/config.py", "eval/fixtures/drift_texts.json"]


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def source_identity():
    files = {}
    for rel in SOURCE_FILES:
        files[rel] = {
            "sha256": sha256_bytes((ROOT / rel).read_bytes()),
            "git_blob": git("hash-object", rel),
        }
    return {"head_commit": git("rev-parse", "HEAD"), "uncommitted_changes": git("status", "--porcelain"), "files": files}


def numeric_settings():
    return {
        "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "cpu_threads": torch.get_num_threads(),
    }


def fix_numeric_settings(threads):
    # Set explicitly (to PyTorch 2.6 defaults) so every configuration and repeat runs under the same flags.
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = True
    torch.set_float32_matmul_precision("highest")
    torch.use_deterministic_algorithms(False)
    torch.backends.cudnn.deterministic = False
    torch.backends.cudnn.benchmark = False
    torch.set_num_threads(threads)


def load_pair(device, dtype):
    models = {}
    for role, name in (("observer", OBSERVER), ("performer", PERFORMER)):
        model = AutoModelForCausalLM.from_pretrained(name, revision=MODEL_REVISIONS[name], dtype=dtype)
        models[role] = model.to(device).eval()
        param = next(models[role].parameters())
        assert param.dtype == dtype and param.device.type == device, (role, param.dtype, param.device)
    return models


def run_configuration(config, repeat, texts, cpu_inputs, ids_sha, budget_deadline):
    device, dtype = CONFIGS[config]
    run = {"config": config, "device": device, "weight_dtype": str(dtype), "repeat": repeat, "texts": {}}
    if device == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    models = load_pair(device, dtype)
    if device == "cuda":
        torch.cuda.synchronize()
    run["load_seconds"] = time.perf_counter() - t0
    run["attn_implementation"] = models["observer"].config._attn_implementation
    print(f"[{config} r{repeat}] loaded in {run['load_seconds']:.2f}s", flush=True)

    fed = {}
    t_run = time.perf_counter()
    for text in texts:
        tid = text["id"]
        if budget_deadline is not None and time.perf_counter() > budget_deadline:
            run["texts"][tid] = {"status": "not_run_budget"}
            print(f"[{config} r{repeat}] {tid} not_run_budget", flush=True)
            continue
        cpu_ids, cpu_mask = cpu_inputs[tid]
        input_ids = cpu_ids.to(device)
        attention_mask = cpu_mask.to(device)
        assert torch.equal(input_ids.cpu(), cpu_ids), tid
        fed[tid] = input_ids.cpu().tolist()
        t_text = time.perf_counter()
        try:
            with torch.inference_mode():
                obs_logits = models["observer"](input_ids=input_ids, attention_mask=attention_mask, use_cache=False).logits
                perf_logits = models["performer"](input_ids=input_ids, attention_mask=attention_mask, use_cache=False).logits
                stats = binoculars_statistics(obs_logits, perf_logits, input_ids, attention_mask)
            values = {k: float(stats[k][0]) for k in STATS}
            record = {"status": "ok", **values, "n_input_tokens": int(stats["n_input_tokens"][0]),
                      "n_scored_tokens": int(stats["n_scored_tokens"][0])}
        except NumericalScoringError as e:
            record = {"status": "error", "error": f"NumericalScoringError: {e}"}
        except torch.OutOfMemoryError as e:
            record = {"status": "error", "error": f"OutOfMemoryError: {e}"}
        if device == "cuda":
            torch.cuda.synchronize()
        record["seconds"] = time.perf_counter() - t_text
        run["texts"][tid] = record
        shown = {k: record[k] for k in STATS} if record["status"] == "ok" else record["error"]
        print(f"[{config} r{repeat}] {tid} {record['status']} {record['seconds']:.3f}s {shown}", flush=True)

    run["score_seconds"] = time.perf_counter() - t_run
    run["fed_input_ids_sha256"] = sha256_bytes(json.dumps([fed[t["id"]] for t in texts if t["id"] in fed]).encode())
    run["input_ids_identical_to_reference_tokenization"] = all(
        torch.equal(torch.tensor(ids), cpu_inputs[tid][0]) for tid, ids in fed.items()
    )
    assert run["input_ids_identical_to_reference_tokenization"], (config, repeat)
    if len(fed) == len(texts):
        assert run["fed_input_ids_sha256"] == ids_sha, (config, repeat)
    del models
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    return run


def compare(run, base):
    """Absolute differences for texts with values in both runs."""
    out = {}
    for stat in STATS:
        diffs = []
        for tid, rec in run["texts"].items():
            ref = base["texts"].get(tid, {})
            if rec.get("status") == "ok" and ref.get("status") == "ok":
                diffs.append((abs(rec[stat] - ref[stat]), tid))
        if diffs:
            values = [d for d, _ in diffs]
            worst = max(diffs)
            out[stat] = {"n_compared": len(diffs), "max_abs_diff": worst[0], "max_at_text": worst[1],
                         "median_abs_diff": statistics.median(values)}
        else:
            out[stat] = {"n_compared": 0}
    return out


def counts(run):
    statuses = [r["status"] for r in run["texts"].values()]
    nonfinite = sum(
        1 for r in run["texts"].values() if r["status"] == "ok" and not all(math.isfinite(r[k]) for k in STATS)
    )
    return {"ok": statuses.count("ok"), "error": statuses.count("error"),
            "not_run_budget": statuses.count("not_run_budget"), "nonfinite_values": nonfinite}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs", nargs="+", choices=CONFIGS, default=list(CONFIGS))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--threads", type=int, default=torch.get_num_threads())
    parser.add_argument("--cpu-budget-seconds", type=float, default=1200.0,
                        help="wall-clock budget for all CPU runs together; remaining texts are recorded not_run_budget")
    args = parser.parse_args()
    if args.repeats < 2:
        raise SystemExit("--repeats must be at least 2")
    if args.configs[0] != REFERENCE[0]:
        raise SystemExit(f"first configuration must be the reference {REFERENCE[0]}")

    started = datetime.now(timezone.utc).astimezone()
    t_start = time.perf_counter()
    print(f"start {started.isoformat()} argv={sys.argv}", flush=True)
    fix_numeric_settings(args.threads)
    settings = numeric_settings()
    print(f"numeric settings: {settings}", flush=True)
    identity = source_identity()
    print(f"source identity: {json.dumps(identity)}", flush=True)

    fixture_bytes = FIXTURE.read_bytes()
    texts = json.loads(fixture_bytes)["texts"]

    tokenizer = AutoTokenizer.from_pretrained(OBSERVER, revision=MODEL_REVISIONS[OBSERVER])
    inputs = {}
    cpu_inputs = {}
    for t in texts:
        full = tokenizer(t["text"], add_special_tokens=False)["input_ids"]
        enc = tokenizer(t["text"], add_special_tokens=False, truncation=True, max_length=MAX_LENGTH, return_tensors="pt")
        if len(full) < 64:
            raise SystemExit(f"{t['id']} has {len(full)} tokens (< 64)")
        inputs[t["id"]] = {"n_tokens": len(full), "n_input_tokens": int(enc["attention_mask"].sum()),
                           "truncated": len(full) > MAX_LENGTH, "input_ids": enc["input_ids"][0].tolist()}
        cpu_inputs[t["id"]] = (enc["input_ids"], enc["attention_mask"])
    ids_sha = sha256_bytes(json.dumps([[inputs[t["id"]]["input_ids"]] for t in texts]).encode())
    print(f"texts={len(texts)} input_ids_sha256={ids_sha} lengths="
          f"{[inputs[t['id']]['n_input_tokens'] for t in texts]}", flush=True)

    unsupported = {}
    if not torch.cuda.is_available():
        for c in [c for c in args.configs if CONFIGS[c][0] == "cuda"]:
            unsupported[c] = "CUDA unavailable"
    elif not torch.cuda.is_bf16_supported():
        unsupported["gpu_bf16"] = "torch.cuda.is_bf16_supported() is False"
    if REFERENCE[0] in unsupported:
        raise SystemExit("reference configuration unavailable")

    runs = []
    cpu_deadline = None
    for config in args.configs:
        if config in unsupported:
            print(f"[{config}] unsupported: {unsupported[config]}", flush=True)
            continue
        for repeat in range(args.repeats):
            deadline = None
            if CONFIGS[config][0] == "cpu":
                if cpu_deadline is None:
                    cpu_deadline = time.perf_counter() + args.cpu_budget_seconds
                deadline = cpu_deadline
            assert numeric_settings() == settings, "numeric settings changed between runs"
            runs.append(run_configuration(config, repeat, texts, cpu_inputs, ids_sha, deadline))

    by_key = {(r["config"], r["repeat"]): r for r in runs}
    reference = by_key[REFERENCE]
    summary = {
        "vs_reference": {
            f"{c}/r{rep}": compare(r, reference) for (c, rep), r in by_key.items() if (c, rep) != REFERENCE
        },
        "run_to_run": {
            f"{c}/r{rep}_vs_r0": compare(r, by_key[(c, 0)]) for (c, rep), r in by_key.items() if rep > 0
        },
        "counts": {f"{c}/r{rep}": counts(r) for (c, rep), r in by_key.items()},
    }
    not_run = {c: unsupported[c] for c in unsupported}
    for c in CONFIGS:
        if c not in args.configs:
            not_run[c] = "not requested"
    not_run.update({
        "cpu_bf16": "not run (not requested)",
        "cpu_fp16": "not run (not requested)",
        "Qwen2.5-1.5B pair": "not run",
        "deployment profile (HF Space)": "not run",
    })

    finished = datetime.now(timezone.utc).astimezone()
    out = {
        "status": "provisional Task 1 drift screening (synthetic texts; not calibration, not threshold-portability "
                  "evidence; D11 Open)",
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "elapsed_seconds": time.perf_counter() - t_start,
        "argv": sys.argv,
        "environment": {
            "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "processor": platform.processor(), "torch": torch.__version__, "torch_cuda": torch.version.cuda,
            "transformers": transformers.__version__,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "numeric_settings": settings,
        "source_identity": identity,
        "fixture": {"path": str(FIXTURE.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_bytes(fixture_bytes),
                    "n_texts": len(texts)},
        "models": {"observer": {"name": OBSERVER, "revision": MODEL_REVISIONS[OBSERVER]},
                   "performer": {"name": PERFORMER, "revision": MODEL_REVISIONS[PERFORMER]}},
        "tokenization": {"tokenizer": f"{OBSERVER}@{MODEL_REVISIONS[OBSERVER]}", "add_special_tokens": False,
                         "truncation": "right", "max_length": MAX_LENGTH, "chat_template": False,
                         "input_ids_sha256": ids_sha},
        "reference": f"{REFERENCE[0]}/r{REFERENCE[1]}",
        "cpu_budget_seconds": args.cpu_budget_seconds,
        "inputs": inputs,
        "runs": runs,
        "summary": summary,
        "unsupported_or_not_run": not_run,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    for key, comp in summary["vs_reference"].items():
        print(f"vs {out['reference']} {key}: " + json.dumps(comp), flush=True)
    for key, comp in summary["run_to_run"].items():
        print(f"run-to-run {key}: " + json.dumps(comp), flush=True)
    print(f"counts: {json.dumps(summary['counts'])}", flush=True)
    print(f"not run / unsupported: {json.dumps(not_run)}", flush=True)
    print(f"finish {finished.isoformat()} elapsed={out['elapsed_seconds']:.1f}s wrote {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
