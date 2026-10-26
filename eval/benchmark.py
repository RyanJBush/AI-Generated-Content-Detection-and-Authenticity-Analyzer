"""Task 1 runtime/memory benchmark through the production scorer (SPEC §3.1, §9).

Loads the pinned observer/performer pair, scores synthetic pilot text at batch size 1 and
increasing token lengths, and times both forward passes plus litmus.binoculars.binoculars_statistics.
Usage: .venv\\Scripts\\python.exe eval\\benchmark.py --pair 0.5b --dtype float32
"""
import argparse
import ctypes
import ctypes.wintypes
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from litmus.binoculars import binoculars_statistics  # noqa: E402
from litmus.config import MODEL_REVISIONS  # noqa: E402

PAIRS = {
    "0.5b": ("Qwen/Qwen2.5-0.5B", "Qwen/Qwen2.5-0.5B-Instruct"),
    "1.5b": ("Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-1.5B-Instruct"),
}
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Synthetic pilot text written for this benchmark (not RAID). Truncated on the right to each length.
PILOT_TEXT = """The harbor town woke slowly on the first cold morning of autumn. Fishing boats knocked against the
pier while gulls argued over the remains of yesterday's catch. Mara walked the length of the seawall with her
hands in her pockets, counting the lamps that had failed overnight. There were seven, two more than last week,
and she wrote the numbers in a small notebook that had once belonged to her father. He had kept the lamps for
thirty years, climbing the iron ladders with a canvas bag of bulbs and fuses, and he had never once let the
whole wall go dark.

The council had promised new fixtures in the spring, then in the summer, and now nobody mentioned them at all.
Mara did not expect much from the council. She expected something from the ledger in the harbor office, where
every purchase since 1962 had been recorded in blue ink. If the bulbs could not be replaced, she wanted to know
where the money for them had gone. The office opened at nine. She had an hour, so she bought coffee from the
kiosk by the ferry ramp and sat on an upturned crate to watch the tide come in.

A ferry from the island arrived early, which was unusual. Most mornings it limped in twenty minutes late, its
engine coughing smoke the colour of wet slate. Today it glided to the ramp as if the sea had been rolled flat
for it. A handful of passengers stepped off: a woman with a cello case, two boys carrying a crate of apples
between them, and a tall man in a grey coat who paused at the bottom of the ramp and looked directly at the
broken lamps, one after another, as though he too were counting.

Mara watched him walk along the wall. He stopped beneath the fourth dead lamp, reached up, and tapped the iron
post twice with his knuckles. Then he took out a notebook of his own, wrote something, and moved on toward the
harbor office. She finished her coffee in one long swallow, which burned, and followed him at a distance that
she hoped looked casual.

The harbor office smelled of tar, paper, and the paraffin heater that had been running since before dawn. The
clerk, a young man named Tobias who had started in the spring, looked up with relief when the stranger came in,
as if he had been expecting him. They spoke quietly at the counter. Mara pretended to read the tide tables on the
wall and listened. The stranger was an engineer from the mainland, sent by the lighting company to survey the
seawall. The company, it seemed, had been paid for new fixtures eighteen months ago. Nobody at the company could
explain why the fixtures had never been installed, and nobody at the council had asked.

Tobias fetched the ledger. It was heavier than Mara remembered, bound in green cloth that had faded to the
colour of moss. The engineer turned the pages carefully, running a finger down the columns of figures. When he
reached the entry he was looking for, he frowned, turned back a page, and then forward again. The payment was
there, signed and dated. Below it, in the same blue ink but a different hand, someone had added a second line
cancelling the order and transferring the money to an account Mara did not recognise.

She stepped forward before she had decided to. The engineer looked at her, then at the notebook in her hand, and
something in his face changed. He asked whether she was the lamp keeper's daughter. She said she was, and that
she had been counting the dark lamps every morning since the funeral. He nodded slowly and slid the ledger across
the counter so that she could read the second line for herself.
"""


def peak_working_set_bytes():
    """Peak host working set of this process (Windows GetProcessMemoryInfo), or None elsewhere."""
    if sys.platform != "win32":
        return None

    class PMC(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.wintypes.DWORD),
            ("PageFaultCount", ctypes.wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = ctypes.wintypes.HANDLE
    get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory_info.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PMC), ctypes.wintypes.DWORD]
    get_memory_info.restype = ctypes.wintypes.BOOL

    counters = PMC()
    counters.cb = ctypes.sizeof(PMC)
    if not get_memory_info(get_current_process(), ctypes.byref(counters), counters.cb):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
    return counters.PeakWorkingSetSize


def device_memory():
    free, total = torch.cuda.mem_get_info()
    return {"device_used_bytes": total - free, "device_total_bytes": total}


def load_model(name, dtype, device):
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(name, revision=MODEL_REVISIONS[name], dtype=dtype)
    model = model.to(device).eval()
    torch.cuda.synchronize()
    seconds = time.perf_counter() - t0
    param = next(model.parameters())
    return model, {
        "name": name,
        "revision": MODEL_REVISIONS[name],
        "load_seconds": seconds,
        "param_dtype": str(param.dtype),
        "param_device": str(param.device),
        "attn_implementation": model.config._attn_implementation,
        "config_vocab_size": model.config.vocab_size,
    }


def score_once(observer, performer, cpu_ids, cpu_mask, device):
    """Timed unit: host-to-device transfer, both forward passes, scorer reductions."""
    input_ids = cpu_ids.to(device)
    attention_mask = cpu_mask.to(device)
    with torch.inference_mode():
        observer_logits = observer(input_ids=input_ids, attention_mask=attention_mask, use_cache=False).logits
        performer_logits = performer(input_ids=input_ids, attention_mask=attention_mask, use_cache=False).logits
        stats = binoculars_statistics(observer_logits, performer_logits, input_ids, attention_mask)
    return stats, observer_logits.shape[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", choices=PAIRS, default="0.5b")
    parser.add_argument("--dtype", choices=["float32", "bfloat16", "float16"], default="float32")
    parser.add_argument("--lengths", type=int, nargs="+", default=[64, 128, 256, 512])
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable; this benchmark does not fall back to CPU")
    device = "cuda"
    dtype = getattr(torch, args.dtype)
    observer_name, performer_name = PAIRS[args.pair]
    started = datetime.now(timezone.utc).astimezone()
    print(f"start {started.isoformat()} pair={args.pair} dtype={args.dtype}", flush=True)

    environment = {
        "argv": sys.argv,
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "transformers": transformers.__version__,
        "gpu": torch.cuda.get_device_name(0),
        "gpu_capability": list(torch.cuda.get_device_capability(0)),
        "tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
        "tf32_cudnn": torch.backends.cudnn.allow_tf32,
        "autocast": False,
        "cpu_threads": torch.get_num_threads(),
    }

    # Download (if needed) separately from load timing.
    downloads = {}
    for name in (observer_name, performer_name):
        t0 = time.perf_counter()
        snapshot_download(name, revision=MODEL_REVISIONS[name])
        downloads[name] = time.perf_counter() - t0
        print(f"snapshot {name}: {downloads[name]:.2f} s", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(observer_name, revision=MODEL_REVISIONS[observer_name])
    full_ids = tokenizer(PILOT_TEXT, add_special_tokens=False)["input_ids"]
    if len(full_ids) < max(args.lengths):
        raise SystemExit(f"pilot text has {len(full_ids)} tokens, fewer than {max(args.lengths)}")

    baseline = device_memory()
    print(f"device memory before load: {baseline}", flush=True)
    observer, observer_info = load_model(observer_name, dtype, device)
    print(f"loaded observer: {observer_info}", flush=True)
    performer, performer_info = load_model(performer_name, dtype, device)
    print(f"loaded performer: {performer_info}", flush=True)
    after_load = {"framework_allocated_bytes": torch.cuda.memory_allocated(), **device_memory()}
    print(f"memory after load: {after_load}", flush=True)

    configurations = []
    for length in args.lengths:
        enc = tokenizer(PILOT_TEXT, add_special_tokens=False, truncation=True, max_length=length,
                        return_tensors="pt")
        cpu_ids, cpu_mask = enc["input_ids"], enc["attention_mask"]
        n_input = int(cpu_mask.sum())

        torch.cuda.synchronize()
        torch.cuda.empty_cache()  # release cached blocks from the previous length so reserved peaks are per length
        torch.cuda.reset_peak_memory_stats()

        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(args.warmup):
            score_once(observer, performer, cpu_ids, cpu_mask, device)
        torch.cuda.synchronize()
        warmup_seconds = time.perf_counter() - t0

        times = []
        stats = logit_dim = None
        for _ in range(args.repeats):
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            stats, logit_dim = score_once(observer, performer, cpu_ids, cpu_mask, device)
            torch.cuda.synchronize()
            times.append(time.perf_counter() - t0)

        result = {
            "n_input_tokens": n_input,
            "n_scored_tokens": int(stats["n_scored_tokens"][0]),
            "logit_dim": logit_dim,
            "warmup_runs": args.warmup,
            "warmup_seconds_total": warmup_seconds,
            "repeats": args.repeats,
            "steady_seconds": times,
            "steady_seconds_median": statistics.median(times),
            "steady_seconds_min": min(times),
            "steady_seconds_max": max(times),
            "max_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
            "max_memory_reserved_bytes": torch.cuda.max_memory_reserved(),
            **device_memory(),
            "pilot_statistics": {k: float(stats[k][0]) for k in ["nll_performer", "nll_observer", "xent", "score"]},
        }
        configurations.append(result)
        print(
            f"len={n_input} scored={result['n_scored_tokens']} logit_dim={logit_dim} "
            f"median={result['steady_seconds_median']:.4f}s min={result['steady_seconds_min']:.4f}s "
            f"max={result['steady_seconds_max']:.4f}s warmup_total={warmup_seconds:.3f}s "
            f"peak_alloc={result['max_memory_allocated_bytes']} peak_reserved={result['max_memory_reserved_bytes']} "
            f"device_used={result['device_used_bytes']} stats={result['pilot_statistics']}",
            flush=True,
        )

    host_peak = peak_working_set_bytes()
    finished = datetime.now(timezone.utc).astimezone()
    out = {
        "status": "provisional Task 1 measurement (synthetic pilot text; not calibration or evaluation data)",
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "pair": args.pair,
        "weight_dtype": args.dtype,
        "device": device,
        "batch_size": 1,
        "tokenization": {"add_special_tokens": False, "truncation": "right", "chat_template": False,
                         "pilot_text_tokens": len(full_ids)},
        "timed_region": "host-to-device transfer of input tensors, observer and performer forward passes "
                        "(use_cache=False), litmus.binoculars.binoculars_statistics incl. validation; "
                        "tokenization excluded",
        "memory_methods": {
            "max_memory_allocated_bytes": "torch.cuda.max_memory_allocated, reset per length; includes resident weights",
            "max_memory_reserved_bytes": "torch.cuda.max_memory_reserved, after empty_cache and reset per length",
            "device_used_bytes": "torch.cuda.mem_get_info total - free (whole device, all processes)",
            "host_peak_working_set_bytes": "Windows GetProcessMemoryInfo PeakWorkingSetSize, whole run",
        },
        "environment": environment,
        "snapshot_seconds": downloads,
        "device_memory_before_load": baseline,
        "models": {"observer": observer_info, "performer": performer_info},
        "memory_after_load": after_load,
        "configurations": configurations,
        "host_peak_working_set_bytes": host_peak,
    }
    path = RESULTS_DIR / f"benchmark_{args.pair}_{args.dtype}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"host_peak_working_set_bytes={host_peak}", flush=True)
    print(f"finish {finished.isoformat()} wrote {path}", flush=True)


if __name__ == "__main__":
    main()
