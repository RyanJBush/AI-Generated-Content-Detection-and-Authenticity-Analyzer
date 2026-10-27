"""R1-A compatibility smoke (NOT the scorer) -> eval/results/r1a_smoke.json.

One forward pass per model on CUDA, fp32 weights, batch size 1, one synthetic
text truncated to exactly 200 tokens. Asserts finite logits, equal vocabulary
dimensions, and the expected dtype/device; records peak GPU memory and the
execution profile. No Binoculars score is computed.

    .venv\\Scripts\\python.exe scripts\\r1a_smoke.py [--out PATH]
"""
import argparse
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch  # noqa: E402  (offline env must be set before import)
import transformers  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DEFAULT_OUT = ROOT / "eval" / "results" / "r1a_smoke.json"
MODELS = ["Qwen2.5-0.5B", "Qwen2.5-0.5B-Instruct"]
N_TOKENS = 200

# Synthetic, deterministic text (no dataset content)
SENTENCES = [
    "The committee met on a grey morning to review the quarterly maintenance plan.",
    "Each department submitted a short list of repairs, ordered by cost and urgency.",
    "Several members asked whether the older pumps could last another winter.",
    "The engineer replied that the bearings were worn but the housings were sound.",
    "After a long discussion, the group agreed to replace two pumps in the spring.",
    "A smaller team will inspect the roof drains and report back within a month.",
    "Funding for the remaining items depends on the outcome of the annual audit.",
]
SYNTHETIC_TEXT = " ".join(SENTENCES * 4)


def nvidia_driver():
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None, "nvidia-smi not found on PATH"
    try:
        proc = subprocess.run(
            [exe, "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"{type(e).__name__}: {e}"
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, f"nvidia-smi exit {proc.returncode}: {proc.stderr.strip()}"
    return proc.stdout.strip().splitlines()[0].strip(), None


def execution_profile():
    driver, driver_error = nvidia_driver()
    profile = {
        "device_type": "cuda",
        "gpu_name": torch.cuda.get_device_name(0),
        "nvidia_driver_version": driver if driver else "unavailable",
        "cuda_runtime_torch": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "os_family": platform.system(),
        "os_platform": platform.platform(),
        "python_version": platform.python_version(),
    }
    # CA2: an undeterminable field makes the profile incomplete
    profile["complete"] = driver is not None
    if driver_error:
        profile["incomplete_reason"] = f"nvidia driver: {driver_error}"
    return profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available; the R1-A smoke requires CUDA")
    device = torch.device("cuda", 0)

    tok = AutoTokenizer.from_pretrained(
        MODELS_DIR / MODELS[0], local_files_only=True, split_special_tokens=True)
    all_ids = tok(SYNTHETIC_TEXT, add_special_tokens=False)["input_ids"]
    if len(all_ids) < N_TOKENS:
        raise SystemExit(f"synthetic text has only {len(all_ids)} tokens")
    input_ids = torch.tensor([all_ids[:N_TOKENS]], device=device)

    torch.cuda.reset_peak_memory_stats(device)
    results = {}
    loaded = []
    for name in MODELS:
        model = AutoModelForCausalLM.from_pretrained(
            MODELS_DIR / name, local_files_only=True, dtype=torch.float32)
        model.to(device).eval()
        loaded.append(model)
        param = next(model.parameters())
        with torch.no_grad():
            logits = model(input_ids=input_ids).logits
        results[name] = {
            "param_dtype": str(param.dtype),
            "param_device": str(param.device),
            "logits_dtype": str(logits.dtype),
            "logits_device": str(logits.device),
            "logits_shape": list(logits.shape),
            "logits_all_finite": bool(torch.isfinite(logits).all().item()),
            "config_vocab_size": model.config.vocab_size,
            "attn_implementation": model.config._attn_implementation,
            "peak_allocated_bytes_after_forward":
                torch.cuda.max_memory_allocated(device),
        }
        del logits

    v = [results[n]["logits_shape"][-1] for n in MODELS]
    checks = {
        "logits_finite": all(results[n]["logits_all_finite"] for n in MODELS),
        "vocab_dims_equal": v[0] == v[1],
        "dtype_float32": all(results[n]["param_dtype"] == "torch.float32"
                             and results[n]["logits_dtype"] == "torch.float32"
                             for n in MODELS),
        "device_cuda": all(results[n]["param_device"] == "cuda:0"
                           and results[n]["logits_device"] == "cuda:0"
                           for n in MODELS),
        "batch1_seq200": all(results[n]["logits_shape"][:2] == [1, N_TOKENS]
                             for n in MODELS),
    }
    out = {
        "check": "r1a_compatibility_smoke",
        "note": "Not the scorer. No Binoculars score computed.",
        "input": {"n_tokens": N_TOKENS, "tokenizer_vocab_size": len(tok),
                  "add_special_tokens": False, "split_special_tokens": True},
        "models": results,
        "peak_gpu_memory_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "execution_profile": execution_profile(),
    }
    path = pathlib.Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["all_checks_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
