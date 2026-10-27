"""R1-A model-dependent checks (slow; excluded by default; run: pytest -m slow).

Requires models/ populated by scripts/download_models.py and, for the smoke
test, CUDA. Missing models make these tests fail, not skip.

The HF trap tests run the loader in a child process because huggingface_hub
reads HF_HUB_OFFLINE and HF_ENDPOINT once, at import time.
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
SCRIPTS = ROOT / "scripts"
MODELS = ["Qwen2.5-0.5B", "Qwen2.5-0.5B-Instruct"]

LOAD_CHILD = r"""
import json, sys
import huggingface_hub.constants as hc
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
models_dir = sys.argv[1]
for name in ("Qwen2.5-0.5B", "Qwen2.5-0.5B-Instruct"):
    path = models_dir + "/" + name
    AutoTokenizer.from_pretrained(path, local_files_only=True)
    AutoModelForCausalLM.from_pretrained(path, local_files_only=True,
                                         dtype=torch.float32)
print(json.dumps({"offline": hc.HF_HUB_OFFLINE, "endpoint": hc.ENDPOINT,
                  "loaded": True}))
"""

CONTROL_CHILD = r"""
import json
import huggingface_hub.constants as hc
from huggingface_hub import HfApi
try:
    HfApi().model_info("Qwen/Qwen2.5-0.5B")
    error = None
except Exception as e:
    error = type(e).__name__
print(json.dumps({"offline": hc.HF_HUB_OFFLINE, "endpoint": hc.ENDPOINT,
                  "error": error}))
"""


def _child_env(tmp_path, trap_url, offline):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("HF_", "TRANSFORMERS_"))}
    env["HF_HOME"] = str(tmp_path / "hf_home")  # no shared cache or token
    env["HF_ENDPOINT"] = trap_url
    if offline:
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
    return env


def _run_child(code, env, *args):
    proc = subprocess.run([sys.executable, "-c", code, *args], env=env,
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_downloaded_files_match_manifest():
    manifest = json.loads((ROOT / "models.manifest.json").read_text(encoding="utf-8"))
    for name in MODELS:
        for rel, meta in manifest[name]["files"].items():
            assert _sha256(MODELS_DIR / name / rel) == meta["sha256"], (name, rel)


# --- A1.4.2 + B4: offline load trap and positive control ---

def test_offline_load_zero_connections(trap, tmp_path):
    env = _child_env(tmp_path, trap.url, offline=True)
    report = _run_child(LOAD_CHILD, env, str(MODELS_DIR))
    print(f"\n[offline load] child={report} trap connections="
          f"{len(trap.connections)} requests={trap.requests}")
    assert report == {"offline": True, "endpoint": trap.url, "loaded": True}
    assert trap.connections == []
    assert trap.requests == []


def test_hub_positive_control_reaches_trap(trap, tmp_path):
    env = _child_env(tmp_path, trap.url, offline=False)
    report = _run_child(CONTROL_CHILD, env)
    print(f"\n[positive control] child={report} trap connections="
          f"{len(trap.connections)} requests={trap.requests}")
    assert report["offline"] is False
    assert report["endpoint"] == trap.url
    assert report["error"] is not None  # the trap answers 404
    assert len(trap.connections) >= 1
    assert any(p.startswith("/api/models/Qwen/Qwen2.5-0.5B") for p in trap.requests)


# --- tokenizer checks and compatibility smoke, via the committed scripts ---

def test_tokenizer_checks(tmp_path):
    out = tmp_path / "tok.json"
    proc = subprocess.run([sys.executable, str(SCRIPTS / "tokenizer_checks.py"),
                           "--out", str(out)], capture_output=True, text=True,
                          timeout=600)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(out.read_text(encoding="utf-8"))
    s = result["summary"]
    assert s["tokenizer_json_identical"] and s["vocab_equal"]
    assert s["added_tokens_equal"] and s["all_probes_models_agree"]
    assert s["all_probes_call_time_settings_agree"]
    assert s["split_special_tokens_changes_ids_for"] == ["literal_special_tokens"]
    # Committed results must match a fresh run
    committed = json.loads((ROOT / "eval" / "results" / "r1a_tokenizer_checks.json")
                           .read_text(encoding="utf-8"))
    assert committed == result


def test_compatibility_smoke_cuda(tmp_path):
    out = tmp_path / "smoke.json"
    proc = subprocess.run([sys.executable, str(SCRIPTS / "r1a_smoke.py"),
                           "--out", str(out)], capture_output=True, text=True,
                          timeout=600)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["all_checks_pass"] is True
    assert result["execution_profile"]["device_type"] == "cuda"
    assert "score" not in json.dumps(result["models"]).lower()
