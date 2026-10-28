"""Model loading, numerical settings and the execution profile (R1-PLAN §1.2, CA2).

Every profile value is READ BACK from the running process after the settings
are applied; nothing requested is recorded unless it is what was observed.
A value that cannot be determined is recorded as "unavailable" and makes the
profile incomplete (CA2).
"""
import ctypes
import ctypes.util
import hashlib
import os
import pathlib
import platform
from dataclasses import dataclass
from typing import Any, Dict, Optional

from litmus import config

UNAVAILABLE = "unavailable"
NOT_APPLICABLE = "not_applicable"
# Model files that must be present for a load (weights are verified at setup)
REQUIRED_FILES = ("config.json", "model.safetensors", "tokenizer.json",
                  "tokenizer_config.json")


class ModelNotInstalled(RuntimeError):
    """Local model files are missing; run scripts/download_models.py."""


def default_models_dir() -> pathlib.Path:
    # src/litmus/scorer/loader.py -> repository root
    return pathlib.Path(__file__).resolve().parents[3] / "models"


def check_installed(models_dir: pathlib.Path) -> None:
    missing = [f"{d}/{f}" for d in (config.OBSERVER_DIR, config.PERFORMER_DIR)
               for f in REQUIRED_FILES if not (models_dir / d / f).is_file()]
    if missing:
        raise ModelNotInstalled(
            "model not installed; run setup (scripts/download_models.py); "
            f"missing: {', '.join(missing)}")


def nvidia_driver_version() -> Optional[str]:
    """NVIDIA driver version via NVML (ctypes, no subprocess); None if unknown."""
    names = ["nvml.dll"] if os.name == "nt" else ["libnvidia-ml.so.1"]
    found = ctypes.util.find_library("nvidia-ml")
    if found:
        names.append(found)
    for name in names:
        try:
            nvml = ctypes.CDLL(name)
        except OSError:
            continue
        try:
            if nvml.nvmlInit_v2() != 0:
                continue
            buf = ctypes.create_string_buffer(80)
            ok = nvml.nvmlSystemGetDriverVersion(buf, ctypes.c_uint(80)) == 0
            nvml.nvmlShutdown()
            if ok and buf.value:
                return buf.value.decode("ascii")
        except (AttributeError, OSError):
            continue
    return None


def apply_numerical_settings():
    """Apply the approved numerical policy. Returns the torch module."""
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", config.CUBLAS_WORKSPACE_CONFIG)
    import torch

    torch.backends.cuda.matmul.allow_tf32 = config.ALLOW_TF32_MATMUL
    torch.backends.cudnn.allow_tf32 = config.ALLOW_TF32_CUDNN
    torch.set_float32_matmul_precision(config.FLOAT32_MATMUL_PRECISION)
    torch.use_deterministic_algorithms(config.DETERMINISTIC_ALGORITHMS)
    return torch


def _sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class LoadedPair:
    tokenizer: Any
    observer: Any
    performer: Any
    device: Any
    profile: Dict[str, Any]
    tokenizer_json_sha256: str
    tokenizer_vocab_size: int
    model_output_dim: int


def read_profile(torch, device, observer, performer) -> Dict[str, Any]:
    """Execution profile read back from the process and the loaded models."""
    import tokenizers
    import transformers

    def model_value(attr_fn):
        values = {attr_fn(observer), attr_fn(performer)}
        return values.pop() if len(values) == 1 else f"mismatch: {sorted(values)}"

    on_cuda = device.type == "cuda"
    driver = nvidia_driver_version() if on_cuda else NOT_APPLICABLE
    profile = {
        "device_type": device.type,
        "gpu_name": torch.cuda.get_device_name(device) if on_cuda else NOT_APPLICABLE,
        "nvidia_driver_version": driver if driver else UNAVAILABLE,
        "cuda_runtime": (torch.version.cuda or UNAVAILABLE) if on_cuda
        else NOT_APPLICABLE,
        # str(): torch.__version__ is a TorchVersion (a str subclass)
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
        "tokenizers_version": str(tokenizers.__version__),
        "attn_implementation": model_value(lambda m: m.config._attn_implementation),
        "batch_size": config.BATCH_SIZE,
        "matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG",
                                                  UNAVAILABLE),
        "weight_dtype": model_value(
            lambda m: str(next(m.parameters()).dtype).removeprefix("torch.")),
        "reduction_dtype": config.REDUCTION_DTYPE,
        "os_family": platform.system() or UNAVAILABLE,
    }
    return profile


def profile_is_complete(profile: Dict[str, Any]) -> bool:
    return all(v != UNAVAILABLE for v in profile.values())


def load_pair(models_dir: Optional[pathlib.Path] = None,
              device: Optional[str] = None) -> LoadedPair:
    models_dir = pathlib.Path(models_dir) if models_dir else default_models_dir()
    check_installed(models_dir)
    # Offline before transformers / huggingface_hub are imported (A1.2)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch = apply_numerical_settings()
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    observer_dir = models_dir / config.OBSERVER_DIR

    tok_sha = _sha256_file(observer_dir / "tokenizer.json")
    if tok_sha != config.TOKENIZER_JSON_SHA256:
        raise RuntimeError(f"tokenizer.json SHA-256 {tok_sha} does not match the "
                           f"pinned {config.TOKENIZER_JSON_SHA256}")
    tokenizer = AutoTokenizer.from_pretrained(observer_dir, local_files_only=True)

    def load(name):
        model = AutoModelForCausalLM.from_pretrained(
            models_dir / name, local_files_only=True,
            dtype=getattr(torch, config.WEIGHT_DTYPE),
            attn_implementation=config.ATTN_IMPLEMENTATION,
        )
        return model.to(dev).eval()

    observer = load(config.OBSERVER_DIR)
    performer = load(config.PERFORMER_DIR)
    out_dims = {observer.config.vocab_size, performer.config.vocab_size}
    if len(out_dims) != 1:
        raise RuntimeError(f"observer/performer output dims differ: {out_dims}")

    return LoadedPair(
        tokenizer=tokenizer, observer=observer, performer=performer, device=dev,
        profile=read_profile(torch, dev, observer, performer),
        tokenizer_json_sha256=tok_sha, tokenizer_vocab_size=len(tokenizer),
        model_output_dim=out_dims.pop(),
    )


def forward_logits(torch, model, ids, device):
    """[T, V] float32 logits for one sequence (batch size 1, no padding)."""
    with torch.inference_mode():
        input_ids = torch.tensor([ids], device=device)
        return model(input_ids=input_ids).logits[0].float()
