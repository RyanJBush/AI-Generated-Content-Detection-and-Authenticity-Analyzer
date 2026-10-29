"""Model loading, numerical settings and the execution profile (R1-PLAN §1.2, CA2).

Every profile value is READ BACK from the running process after the settings
are applied; nothing requested is recorded unless it is what was observed.
A value that cannot be determined is recorded as "unavailable" and makes the
profile incomplete (CA2); profile_failures() is the explicit completeness check
against PROFILE_SCHEMA. configure_numerics() must run before CUDA initializes.
"""
import ctypes
import ctypes.util
import hashlib
import os
import pathlib
import platform
import re
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


# torch.cuda.is_initialized() as observed by the FIRST configure_numerics call
# for each device type in this process. Absent -> order not established.
_CUDA_INITIALIZED_AT_CONFIGURE: Dict[str, bool] = {}


def configure_numerics(device_type: str):
    """Set every numerical setting; must run before any CUDA/cuBLAS init.

    Records whether CUDA was already initialized when it ran: an environment
    variable read back later is not proof it was in force (cuBLAS reads
    CUBLAS_WORKSPACE_CONFIG once, at its own initialization). Returns torch.
    """
    import torch  # importing torch does not initialize CUDA

    initialized = bool(torch.cuda.is_initialized())
    if device_type == "cuda" and config.DETERMINISTIC_ALGORITHMS:
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = config.CUBLAS_WORKSPACE_CONFIG
    torch.backends.cuda.matmul.allow_tf32 = config.ALLOW_TF32_MATMUL
    torch.backends.cudnn.allow_tf32 = config.ALLOW_TF32_CUDNN
    torch.set_float32_matmul_precision(config.FLOAT32_MATMUL_PRECISION)
    torch.use_deterministic_algorithms(config.DETERMINISTIC_ALGORITHMS)
    _CUDA_INITIALIZED_AT_CONFIGURE.setdefault(device_type, initialized)
    return torch


def cuda_initialized_at_configure(device_type: str):
    """The recorded order for device_type, or UNAVAILABLE if never configured."""
    return _CUDA_INITIALIZED_AT_CONFIGURE.get(device_type, UNAVAILABLE)


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


def model_settings(model) -> Dict[str, str]:
    """Settings read from one loaded model."""
    return {
        "attn_implementation": model.config._attn_implementation,
        "weight_dtype": str(next(model.parameters()).dtype).removeprefix("torch."),
    }


def effective_settings(torch, device_type: str, observer, performer
                       ) -> Dict[str, Any]:
    """Settings that can change after load, read from the process and models.
    Used for the profile at load and re-read before every scoring call."""
    def model_value(key):
        values = {model_settings(observer)[key], model_settings(performer)[key]}
        return values.pop() if len(values) == 1 else f"mismatch: {sorted(values)}"

    return {
        "attn_implementation": model_value("attn_implementation"),
        "matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG",
                                                  UNAVAILABLE)
        if device_type == "cuda" else NOT_APPLICABLE,
        "weight_dtype": model_value("weight_dtype"),
    }


def profile_changes(profile: Dict[str, Any], effective: Dict[str, Any]
                    ) -> Dict[str, Dict[str, Any]]:
    """Fields whose effective value differs from the profile used for the hash."""
    return {k: {"profile": profile.get(k), "effective": v}
            for k, v in effective.items() if profile.get(k) != v}


def read_profile(torch, device, observer, performer) -> Dict[str, Any]:
    """Execution profile read back from the process and the loaded models."""
    import tokenizers
    import transformers

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
        "batch_size": config.BATCH_SIZE,
        "reduction_dtype": config.REDUCTION_DTYPE,
        "os_family": platform.system() or UNAVAILABLE,
        "cuda_initialized_before_settings": cuda_initialized_at_configure(
            device.type),
    }
    profile.update(effective_settings(torch, device.type, observer, performer))
    return profile


# --- profile completeness (Corrections A CA2; R1-B1 corrections Fix 1) ---

CUDA_ORDER_REASON = "cuda_initialized_before_settings"
# The only fields that may be "not_applicable", and only on CPU
GPU_FIELDS = ("gpu_name", "nvidia_driver_version", "cuda_runtime",
              "cublas_workspace_config")
NOT_MEASURED = {UNAVAILABLE, "unknown"}
_VERSION = re.compile(r"\d+(\.\d+)+([.+\-][0-9A-Za-z.+\-]*)?")  # 2.6.0+cu124
_DRIVER = re.compile(r"\d+(\.\d+)+")  # 572.60
_CUDA_RUNTIME = re.compile(r"\d+\.\d+")  # 12.4


def _pinned(value):
    return lambda v: type(v) is type(value) and v == value


def _matches(pattern):
    return lambda v: isinstance(v, str) and pattern.fullmatch(v) is not None


# Permitted values per required field (values on CUDA; see GPU_FIELDS for CPU)
PROFILE_SCHEMA = {
    "device_type": lambda v: v in ("cuda", "cpu"),
    "gpu_name": lambda v: isinstance(v, str) and v.strip() != "",
    "nvidia_driver_version": _matches(_DRIVER),
    "cuda_runtime": _matches(_CUDA_RUNTIME),
    "torch_version": _matches(_VERSION),
    "transformers_version": _matches(_VERSION),
    "tokenizers_version": _matches(_VERSION),
    "attn_implementation": _pinned(config.ATTN_IMPLEMENTATION),
    "batch_size": _pinned(config.BATCH_SIZE),
    "matmul_allow_tf32": _pinned(config.ALLOW_TF32_MATMUL),
    "cudnn_allow_tf32": _pinned(config.ALLOW_TF32_CUDNN),
    "float32_matmul_precision": _pinned(config.FLOAT32_MATMUL_PRECISION),
    "deterministic_algorithms": lambda v: type(v) is bool,
    "cublas_workspace_config": _pinned(config.CUBLAS_WORKSPACE_CONFIG),
    "weight_dtype": _pinned(config.WEIGHT_DTYPE),
    "reduction_dtype": _pinned(config.REDUCTION_DTYPE),
    "os_family": lambda v: v in ("Windows", "Linux", "Darwin"),
    "cuda_initialized_before_settings": _pinned(False),
}


def _value_failure(name: str, value: Any, device_type: Any) -> Optional[str]:
    if value is None:
        return "None"
    if isinstance(value, str) and value.strip() == "":
        return "empty string"
    if isinstance(value, str) and value.strip().lower() in NOT_MEASURED:
        return f"not measured ({value!r})"
    gpu_on_cpu = name in GPU_FIELDS and device_type == "cpu"
    if value == NOT_APPLICABLE:
        return None if gpu_on_cpu else (
            "not_applicable is permitted only for GPU-specific fields on cpu")
    if gpu_on_cpu:
        return f"must be not_applicable on cpu, got {value!r}"
    if not PROFILE_SCHEMA[name](value):
        return f"value {value!r} outside permitted set"
    return None


def profile_failures(profile: Dict[str, Any], models=()) -> Dict[str, str]:
    """Failing fields -> reason; empty means complete. ``models``: loaded
    (name, model) pairs whose settings the profile must agree with."""
    if not profile:
        return {"<profile>": "empty profile"}
    failures = {k: "unexpected field" for k in profile if k not in PROFILE_SCHEMA}
    device_type = profile.get("device_type")
    for name in PROFILE_SCHEMA:
        if name not in profile:
            failures[name] = "missing"
            continue
        reason = _value_failure(name, profile[name], device_type)
        if reason:
            failures[name] = reason
    if "cuda_initialized_before_settings" in failures:
        failures["cuda_initialized_before_settings"] = CUDA_ORDER_REASON
    for model_name, model in models:
        for key, value in model_settings(model).items():
            if profile.get(key) != value:
                failures[key] = (f"profile {profile.get(key)!r} differs from the "
                                 f"loaded {model_name} model ({value!r})")
    return dict(sorted(failures.items()))


def profile_is_complete(profile: Dict[str, Any], models=()) -> bool:
    return not profile_failures(profile, models)


def load_pair(models_dir: Optional[pathlib.Path] = None,
              device: Optional[str] = None) -> LoadedPair:
    models_dir = pathlib.Path(models_dir) if models_dir else default_models_dir()
    check_installed(models_dir)
    # Offline before transformers / huggingface_hub are imported (A1.2)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch

    # torch.cuda.is_available() does not initialize CUDA
    dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    configure_numerics(dev.type)  # before anything touches the device
    from transformers import AutoModelForCausalLM, AutoTokenizer

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
