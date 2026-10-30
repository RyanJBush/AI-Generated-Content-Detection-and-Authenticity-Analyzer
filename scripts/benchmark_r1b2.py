"""R1-B2 synthetic runtime and GPU-memory benchmark -> eval/results/r1b2_benchmark.json.

Measures, on the pinned CUDA / fp32 / eager / TF32-off / batch-1 profile and
through the production scorer code paths (litmus.scorer.*):

- model load (3 separate fresh processes, plus the measuring process's own load)
- tokenization: the production tokenizer call alone, per text (CPU)
- scoring: synchronize; IDs to GPU; two forward passes; float32 log-softmax and
  full-vocabulary reductions with validation guards; scalars to host;
  synchronize (exactly the sequence in BinocularsAnalyzer.score_text)
- end-to-end: BinocularsAnalyzer on an already-decoded string (tokenization +
  settings re-read + scoring + OriginEvidence assembly), no model load or input
  file I/O
- peak GPU memory per length block

Inputs: eval/inputs/r1b2/ (scripts/r1b2_inputs.py). The benchmark is not a test.

    .venv\\Scripts\\python.exe scripts\\benchmark_r1b2.py [--out PATH]
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import math
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
INPUTS = ROOT / "eval" / "inputs" / "r1b2"
DEFAULT_OUT = ROOT / "eval" / "results" / "r1b2_benchmark.json"
LOAD_PROCESSES = 3
WARMUP_CALLS = 5
TIMED_PASSES = 3


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def summarize(values):
    """min / median / mean / p90 (nearest rank) / max, in seconds."""
    s = sorted(values)
    rank = max(1, math.ceil(0.9 * len(s)))
    return {"n": len(s), "min": s[0], "median": statistics.median(s),
            "mean": statistics.fmean(s), "p90": s[rank - 1], "max": s[-1]}


# --- system information (outside timed regions and outside offline guards) ---

def cpu_name():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    except OSError:
        return "unavailable"


def ram_bytes():
    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return "unavailable"
    return status.ullTotalPhys


def power_state():
    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte),
                    ("SystemStatusFlag", ctypes.c_ubyte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong)]
    s = SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
        return {"ac_line": "unavailable"}
    ac = {0: "offline (battery)", 1: "online (AC)"}.get(s.ACLineStatus, "unknown")
    plan = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True,
                          text=True)
    return {"ac_line": ac, "battery_percent": s.BatteryLifePercent,
            "battery_flag": s.BatteryFlag,
            "power_plan": plan.stdout.strip() if plan.returncode == 0
            else f"unavailable (exit {plan.returncode})"}


def gpu_sample():
    """nvidia-smi snapshot (temperature, clocks, power, memory) for context."""
    fields = "temperature.gpu,clocks.sm,clocks.mem,power.draw,pstate,memory.used"
    proc = subprocess.run(["nvidia-smi", f"--query-gpu={fields}",
                           "--format=csv,noheader"], capture_output=True, text=True)
    return {"time": now(), "exit": proc.returncode,
            "query": fields, "value": proc.stdout.strip()}


def compute_apps():
    proc = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,"
                           "used_memory", "--format=csv"], capture_output=True,
                          text=True)
    return {"exit": proc.returncode, "output": proc.stdout.strip()}


# --- model load ---

def timed_load():
    """Load both models + tokenizer and verify settings; returns (pair, record)."""
    t_import = time.perf_counter()
    import torch
    import transformers  # noqa: F401  (import cost kept out of the load time)

    from litmus.scorer.loader import load_pair, profile_failures
    import_s = time.perf_counter() - t_import

    t0 = time.perf_counter()
    pair = load_pair(device="cuda")
    torch.cuda.synchronize()
    failures = profile_failures(pair.profile, models=(
        ("observer", pair.observer), ("performer", pair.performer)))
    on_gpu_eval = all(next(m.parameters()).device.type == "cuda" and not m.training
                      for m in (pair.observer, pair.performer))
    load_s = time.perf_counter() - t0
    return pair, {"load_seconds": load_s, "import_seconds": import_s,
                  "profile_failures": failures, "models_on_gpu_eval": on_gpu_eval,
                  "memory_allocated_after_load": torch.cuda.memory_allocated(),
                  "memory_reserved_after_load": torch.cuda.memory_reserved()}


def load_only():
    started = now()
    _, rec = timed_load()
    rec.update(started=started, finished=now(), pid=os.getpid())
    print(json.dumps(rec))
    return 0


def fresh_process_loads():
    runs = []
    for i in range(LOAD_PROCESSES):
        proc = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()),
                               "--load-only"], capture_output=True, text=True,
                              cwd=ROOT)
        rec = {"process": i + 1, "exit": proc.returncode}
        if proc.returncode == 0:
            rec.update(json.loads(proc.stdout.strip().splitlines()[-1]))
        else:
            rec["stderr_tail"] = proc.stderr[-2000:]
        print(f"[load process {i + 1}] exit={proc.returncode} "
              f"load_seconds={rec.get('load_seconds')}", flush=True)
        runs.append(rec)
    return runs


# --- per-length measurements ---

def load_inputs():
    manifest = json.loads((INPUTS / "manifest.json").read_text(encoding="utf-8"))
    by_length = {}
    for e in manifest["files"]:
        data = (INPUTS / e["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != e["sha256"]:
            raise SystemExit(f"{e['file']}: SHA-256 differs from the manifest")
        by_length.setdefault(e["target_tokens"], []).append(
            (e["file"], data.decode("utf-8")))
    return manifest, by_length


def measure_length(torch, pair, analyzer, n_tokens, texts, errors):
    from litmus import config
    from litmus.offline import offline_guards
    from litmus.scorer.analyzer import NO_CALIBRATION
    from litmus.scorer.binoculars import binoculars_statistics
    from litmus.scorer.loader import forward_logits
    from litmus.scorer.tokenize import tokenize_window

    def tokenize(text):
        t0 = time.perf_counter()
        pair.tokenizer(text, add_special_tokens=config.ADD_SPECIAL_TOKENS,
                       split_special_tokens=config.SPLIT_SPECIAL_TOKENS,
                       return_offsets_mapping=True)
        return time.perf_counter() - t0

    def score(ids):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        obs = forward_logits(torch, pair.observer, ids, pair.device)
        perf = forward_logits(torch, pair.performer, ids, pair.device)
        stats = binoculars_statistics(obs, perf, torch.tensor(ids, device=pair.device))
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - t0
        del obs, perf
        return elapsed, stats["score"]

    def end_to_end(text):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        ev = analyzer(text)
        torch.cuda.synchronize()
        return time.perf_counter() - t0, ev

    windows = {}
    for name, text in texts:
        w = tokenize_window(pair.tokenizer, text)
        if w.tokens_total != n_tokens or w.truncated:
            errors.append({"length": n_tokens, "file": name, "phase": "input",
                           "error": f"tokens_total={w.tokens_total} "
                                    f"truncated={w.truncated}"})
        windows[name] = w.ids

    block = {"length": n_tokens, "gpu_before": gpu_sample(), "started": now()}
    torch.cuda.reset_peak_memory_stats()
    block["memory_allocated_before_scoring"] = torch.cuda.memory_allocated()
    block["memory_reserved_before_scoring"] = torch.cuda.memory_reserved()
    raw = {"tokenization": [], "scoring": [], "end_to_end": []}
    calls = []
    with offline_guards():
        for name, _ in texts[:WARMUP_CALLS]:
            try:
                score(windows[name])
            except Exception as e:  # reported, never dropped
                errors.append({"length": n_tokens, "file": name, "phase": "warmup",
                               "error": repr(e)})
        for p in range(TIMED_PASSES):
            for name, text in texts:
                call = {"pass": p + 1, "file": name}
                for phase, fn in (("tokenization", lambda: tokenize(text)),
                                  ("scoring", lambda: score(windows[name])),
                                  ("end_to_end", lambda: end_to_end(text))):
                    try:
                        out = fn()
                    except Exception as e:
                        errors.append({"length": n_tokens, "file": name,
                                       "pass": p + 1, "phase": phase,
                                       "error": repr(e)})
                        continue
                    if phase == "tokenization":
                        raw[phase].append(out)
                        continue
                    seconds, result = out
                    raw[phase].append(seconds)
                    if phase == "scoring":
                        call["scoring_score"] = result
                    else:
                        call["e2e_raw_score"] = result.raw_score
                        call["e2e_result"] = result.result.value
                        call["e2e_reasons"] = result.reasons
                        if (result.result.value != "inconclusive"
                                or result.reasons != [NO_CALIBRATION]
                                or result.raw_score is None):
                            errors.append({"length": n_tokens, "file": name,
                                           "pass": p + 1, "phase": phase,
                                           "error": "unexpected evidence: "
                                                    f"{result.result.value} "
                                                    f"{result.reasons}"})
                calls.append(call)
    block["finished"] = now()
    block["peak_memory_allocated"] = torch.cuda.max_memory_allocated()
    block["peak_memory_reserved"] = torch.cuda.max_memory_reserved()
    block["gpu_after"] = gpu_sample()
    block["summary_seconds"] = {k: summarize(v) for k, v in raw.items() if v}
    block["raw_seconds"] = raw
    scores = {}
    for c in calls:
        scores.setdefault(c["file"], set()).update(
            v for k, v in c.items() if k in ("scoring_score", "e2e_raw_score"))
    block["score_consistency"] = {
        "texts": len(scores),
        "texts_with_one_distinct_score": sum(len(s) == 1 for s in scores.values())}
    block["calls"] = calls
    return block


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--load-only", action="store_true",
                    help="internal: one timed load in this fresh process")
    args = ap.parse_args(argv)
    if args.load_only:
        return load_only()

    started = now()
    system = {"cpu": cpu_name(), "ram_bytes": ram_bytes(),
              "os": platform.platform(), "python": platform.python_version(),
              "power": power_state(), "compute_apps_before": compute_apps(),
              "gpu_at_start": gpu_sample()}
    manifest, by_length = load_inputs()

    loads = fresh_process_loads()

    # This process: settings are applied inside load_pair before CUDA init
    pair, main_load = timed_load()
    import torch

    from litmus.scorer import identity
    from litmus.scorer.analyzer import BinocularsAnalyzer

    if main_load["profile_failures"]:
        raise SystemExit(f"profile incomplete: {main_load['profile_failures']}")
    fields = identity.config_fields(pair.profile,
                                    identity.static_fields(pair.tokenizer_json_sha256),
                                    list(identity.SOURCE_FILES),
                                    identity.source_sha256())
    props = torch.cuda.get_device_properties(pair.device)
    system["gpu_total_vram_bytes"] = props.total_memory
    analyzer = BinocularsAnalyzer(device="cuda")
    analyzer._pair = pair

    errors = []
    blocks = []
    for n in sorted(by_length):
        print(f"[length {n}] {len(by_length[n])} texts", flush=True)
        blocks.append(measure_length(torch, pair, analyzer, n, by_length[n], errors))
        s = blocks[-1]["summary_seconds"]
        print("  " + "  ".join(f"{k}: median={v['median']:.4f}s p90={v['p90']:.4f}s"
                               for k, v in s.items()), flush=True)

    result = {
        "checkpoint": "R1-B2",
        "started": started, "finished": now(),
        "command": " ".join([sys.executable] + sys.argv),
        "definitions": {
            "timer": "time.perf_counter()",
            "p90": "nearest rank: the ceil(0.9*n)-th smallest value",
            "model_load": "load_pair(device='cuda') (tokenizer + both models from "
                          "models/, local_files_only, settings applied before CUDA "
                          "init) + torch.cuda.synchronize() + profile_failures() "
                          "== {} and both models on GPU in eval mode; torch and "
                          "transformers imports timed separately",
            "tokenization": "the production tokenizer call (add_special_tokens="
                            "False, split_special_tokens=True, offsets) alone",
            "scoring": "synchronize; forward_logits x2 (IDs to GPU); "
                       "binoculars_statistics (float32 log-softmax, full-vocabulary "
                       "reductions, validation guards, scalars to host); synchronize",
            "end_to_end": "BinocularsAnalyzer(text) with the loaded pair, between "
                          "two synchronize calls: tokenization, settings re-read, "
                          "scoring, OriginEvidence assembly (includes hashing the 7 "
                          "source files for scoring_config); excludes model load "
                          "and input file I/O",
            "warmup": f"{WARMUP_CALLS} untimed scoring calls per length",
            "timed": f"{TIMED_PASSES} passes x 10 texts per length",
            "memory": "torch.cuda.reset_peak_memory_stats() before each length "
                      "block; max_memory_allocated / max_memory_reserved after it",
            "offline": "each length block runs under litmus.offline.offline_guards()",
        },
        "system": system,
        "execution_profile": pair.profile,
        "execution_profile_failures": main_load["profile_failures"],
        "scoring_config_hash": identity.scoring_config_hash(fields),
        "source_sha256": fields["source_sha256"],
        "inputs": {"dir": "eval/inputs/r1b2", "manifest_sha256": hashlib.sha256(
            (INPUTS / "manifest.json").read_bytes()).hexdigest(),
            "base_seed": manifest["base_seed"]},
        "model_load_fresh_processes": loads,
        "model_load_measuring_process": main_load,
        "lengths": blocks,
        "errors": errors,
        "gpu_at_end": gpu_sample(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"errors: {len(errors)}")
    print(f"wrote {args.out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
