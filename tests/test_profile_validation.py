"""Execution-profile completeness, initialization order and pre-scoring re-read
(R1-B1 corrections, Fixes 1 and 3). Model-free; no CUDA is initialized."""
from types import SimpleNamespace

import pytest

from litmus import config
from litmus.scorer import loader
from litmus.scorer.analyzer import (
    NO_CALIBRATION,
    PROFILE_CHANGED,
    PROFILE_INCOMPLETE,
    BinocularsAnalyzer,
    evidence_from_score,
)
from litmus.scorer.loader import (
    CUDA_ORDER_REASON,
    GPU_FIELDS,
    NOT_APPLICABLE,
    PROFILE_SCHEMA,
    UNAVAILABLE,
    profile_failures,
    profile_is_complete,
)

# Fixed test inputs, not measurements
CUDA_PROFILE = {
    "device_type": "cuda",
    "gpu_name": "Test GPU",
    "nvidia_driver_version": "572.60",
    "cuda_runtime": "12.4",
    "torch_version": "2.6.0+cu124",
    "transformers_version": "4.57.6",
    "tokenizers_version": "0.22.2",
    "attn_implementation": "eager",
    "batch_size": 1,
    "matmul_allow_tf32": False,
    "cudnn_allow_tf32": False,
    "float32_matmul_precision": "highest",
    "deterministic_algorithms": True,
    "cublas_workspace_config": ":4096:8",
    "weight_dtype": "float32",
    "reduction_dtype": "float32",
    "os_family": "Windows",
    "cuda_initialized_before_settings": False,
}
CPU_PROFILE = dict(CUDA_PROFILE, device_type="cpu",
                   **{f: NOT_APPLICABLE for f in GPU_FIELDS})
NON_GPU_FIELDS = [f for f in PROFILE_SCHEMA if f not in GPU_FIELDS]


def without(profile, key):
    return {k: v for k, v in profile.items() if k != key}


class FakeModel:
    """Exposes only what the profile reads; scoring it is a test failure."""

    def __init__(self, attn="eager", dtype="float32"):
        import torch
        self.config = SimpleNamespace(_attn_implementation=attn)
        self._param = torch.zeros(1, dtype=getattr(torch, dtype))

    def parameters(self):
        yield self._param

    def __call__(self, **kwargs):
        raise AssertionError("the model must not be run")


# --- Fix 1: required-field schema ---

def test_schema_keys_are_exactly_the_hashed_profile_fields():
    from litmus.scorer.identity import PROFILE_FIELDS
    assert set(PROFILE_SCHEMA) == set(PROFILE_FIELDS)


def test_valid_cuda_profile_is_complete():
    assert profile_failures(CUDA_PROFILE) == {}
    assert profile_is_complete(CUDA_PROFILE)


def test_valid_cpu_profile_with_not_applicable_is_complete():
    assert profile_failures(CPU_PROFILE) == {}


@pytest.mark.parametrize("field", NON_GPU_FIELDS)
def test_not_applicable_on_a_non_gpu_field_fails(field):
    failures = profile_failures(dict(CPU_PROFILE, **{field: NOT_APPLICABLE}))
    assert field in failures


@pytest.mark.parametrize("field", GPU_FIELDS)
def test_not_applicable_on_a_gpu_field_fails_on_cuda(field):
    assert field in profile_failures(dict(CUDA_PROFILE, **{field: NOT_APPLICABLE}))


@pytest.mark.parametrize("field", GPU_FIELDS)
def test_gpu_field_must_be_not_applicable_on_cpu(field):
    assert field in profile_failures(dict(CPU_PROFILE, **{field: CUDA_PROFILE[field]}))


# (kind, profile, failing field)
FAILURES = [
    ("empty profile", {}, "<profile>"),
    ("missing key", without(CUDA_PROFILE, "torch_version"), "torch_version"),
    ("extra key", dict(CUDA_PROFILE, surprise=1), "surprise"),
    ("None", dict(CUDA_PROFILE, gpu_name=None), "gpu_name"),
    ("empty string", dict(CUDA_PROFILE, tokenizers_version=""), "tokenizers_version"),
    ("blank string", dict(CUDA_PROFILE, gpu_name="  "), "gpu_name"),
    ("unavailable", dict(CUDA_PROFILE, nvidia_driver_version=UNAVAILABLE),
     "nvidia_driver_version"),
    ("unknown", dict(CUDA_PROFILE, os_family="unknown"), "os_family"),
    ("device_type", dict(CUDA_PROFILE, device_type="tpu"), "device_type"),
    ("batch_size", dict(CUDA_PROFILE, batch_size=2), "batch_size"),
    ("batch_size bool", dict(CUDA_PROFILE, batch_size=True), "batch_size"),
    ("attention", dict(CUDA_PROFILE, attn_implementation="sdpa"),
     "attn_implementation"),
    ("matmul tf32 on", dict(CUDA_PROFILE, matmul_allow_tf32=True), "matmul_allow_tf32"),
    ("cudnn tf32 on", dict(CUDA_PROFILE, cudnn_allow_tf32=True), "cudnn_allow_tf32"),
    ("tf32 not bool", dict(CUDA_PROFILE, cudnn_allow_tf32=0), "cudnn_allow_tf32"),
    ("precision", dict(CUDA_PROFILE, float32_matmul_precision="high"),
     "float32_matmul_precision"),
    ("deterministic not bool", dict(CUDA_PROFILE, deterministic_algorithms="yes"),
     "deterministic_algorithms"),
    ("cublas", dict(CUDA_PROFILE, cublas_workspace_config=":16:8"),
     "cublas_workspace_config"),
    ("weight dtype", dict(CUDA_PROFILE, weight_dtype="bfloat16"), "weight_dtype"),
    ("reduction dtype", dict(CUDA_PROFILE, reduction_dtype="float64"),
     "reduction_dtype"),
    ("version format", dict(CUDA_PROFILE, torch_version="latest"), "torch_version"),
    ("version type", dict(CUDA_PROFILE, transformers_version=4.57),
     "transformers_version"),
    ("driver format", dict(CUDA_PROFILE, nvidia_driver_version="r572"),
     "nvidia_driver_version"),
    ("cuda runtime format", dict(CUDA_PROFILE, cuda_runtime="12"), "cuda_runtime"),
    ("os family", dict(CUDA_PROFILE, os_family="Plan9"), "os_family"),
    ("model mismatch", dict(CUDA_PROFILE, attn_implementation="mismatch: [...]"),
     "attn_implementation"),
]


@pytest.mark.parametrize("kind, profile, field", FAILURES,
                         ids=[k for k, _, _ in FAILURES])
def test_each_failure_kind_makes_the_profile_incomplete(kind, profile, field):
    failures = profile_failures(profile)
    assert field in failures, failures
    assert not profile_is_complete(profile)


@pytest.mark.parametrize("model_kw, field", [
    ({"attn": "sdpa"}, "attn_implementation"),
    ({"dtype": "bfloat16"}, "weight_dtype"),
])
def test_profile_differing_from_the_loaded_model_is_incomplete(model_kw, field):
    models = (("observer", FakeModel()), ("performer", FakeModel(**model_kw)))
    assert profile_failures(CUDA_PROFILE, models=(models[0],)) == {}
    failures = profile_failures(CUDA_PROFILE, models=models)
    assert list(failures) == [field]
    assert "performer" in failures[field]


def test_incomplete_evidence_lists_failing_fields(tmp_path):
    profile = dict(CUDA_PROFILE, gpu_name=UNAVAILABLE, batch_size=4)
    stats = {"nll_performer": 2.0, "xent": 2.5, "score": 0.8,
             "n_input_tokens": 100, "n_target_tokens": 99}
    window = {"tokens_total": 100, "tokens_scored": 100, "truncated": False,
              "scored_char_range": [0, 400]}
    ev = evidence_from_score(stats, window, profile, None, None, 151665, 151936,
                             tmp_path / "none")
    assert ev.result.value == "inconclusive"
    assert ev.reasons == [PROFILE_INCOMPLETE]
    assert sorted(ev.details["execution_profile_failures"]) == [
        "batch_size", "gpu_name"]
    assert ev.details["execution_profile_complete"] is False


# --- Fix 3: settings before CUDA initialization ---

@pytest.fixture
def numerics(monkeypatch):
    """Fresh order record; torch settings and the env var restored afterwards."""
    import torch
    saved = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32,
             torch.get_float32_matmul_precision(),
             torch.are_deterministic_algorithms_enabled())
    monkeypatch.setattr(loader, "_CUDA_INITIALIZED_AT_CONFIGURE", {})
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    yield torch
    torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = saved[:2]
    torch.set_float32_matmul_precision(saved[2])
    torch.use_deterministic_algorithms(saved[3])


def test_order_not_established_without_configuration(numerics):
    assert loader.cuda_initialized_at_configure("cuda") == UNAVAILABLE
    profile = dict(CUDA_PROFILE, cuda_initialized_before_settings=UNAVAILABLE)
    assert profile_failures(profile) == {
        "cuda_initialized_before_settings": CUDA_ORDER_REASON}


def test_configure_before_cuda_init_is_complete(numerics, monkeypatch):
    torch = numerics
    monkeypatch.setattr(torch.cuda, "is_initialized", lambda: False)
    loader.configure_numerics("cuda")
    assert loader.cuda_initialized_at_configure("cuda") is False
    assert torch.backends.cuda.matmul.allow_tf32 is False
    assert torch.backends.cudnn.allow_tf32 is False
    assert torch.get_float32_matmul_precision() == "highest"
    assert torch.are_deterministic_algorithms_enabled() is True
    import os
    assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == config.CUBLAS_WORKSPACE_CONFIG
    profile = dict(CUDA_PROFILE, cuda_initialized_before_settings=(
        loader.cuda_initialized_at_configure("cuda")))
    assert profile_is_complete(profile)


def test_configure_after_cuda_init_is_incomplete(numerics, monkeypatch, tmp_path):
    monkeypatch.setattr(numerics.cuda, "is_initialized", lambda: True)
    loader.configure_numerics("cuda")
    recorded = loader.cuda_initialized_at_configure("cuda")
    assert recorded is True
    profile = dict(CUDA_PROFILE, cuda_initialized_before_settings=recorded)
    assert profile_failures(profile) == {
        "cuda_initialized_before_settings": CUDA_ORDER_REASON}
    stats = {"nll_performer": 2.0, "xent": 2.5, "score": 0.8,
             "n_input_tokens": 100, "n_target_tokens": 99}
    window = {"tokens_total": 100, "tokens_scored": 100, "truncated": False,
              "scored_char_range": [0, 400]}
    ev = evidence_from_score(stats, window, profile, None, None, 151665, 151936,
                             tmp_path / "none")
    assert ev.reasons == [PROFILE_INCOMPLETE, CUDA_ORDER_REASON]


def test_first_configuration_fixes_the_recorded_order(numerics, monkeypatch):
    state = {"initialized": False}
    monkeypatch.setattr(numerics.cuda, "is_initialized", lambda: state["initialized"])
    loader.configure_numerics("cuda")
    state["initialized"] = True
    loader.configure_numerics("cuda")  # a later call cannot rewrite history
    assert loader.cuda_initialized_at_configure("cuda") is False


def test_cpu_configuration_does_not_set_cublas(numerics, monkeypatch):
    import os
    monkeypatch.setattr(numerics.cuda, "is_initialized", lambda: False)
    loader.configure_numerics("cpu")
    assert "CUBLAS_WORKSPACE_CONFIG" not in os.environ
    assert loader.cuda_initialized_at_configure("cpu") is False
    assert loader.cuda_initialized_at_configure("cuda") == UNAVAILABLE


class CharTokenizer:
    """One token per character (enough for tokenize_window)."""

    def __call__(self, text, **kwargs):
        return {"input_ids": [ord(c) % 1000 for c in text],
                "offset_mapping": [(i, i + 1) for i in range(len(text))]}


def _loaded_cpu_pair(torch):
    observer, performer = FakeModel(), FakeModel()
    profile = dict(CPU_PROFILE, cuda_initialized_before_settings=False)
    profile.update(loader.effective_settings(torch, "cpu", observer, performer))
    assert profile_is_complete(profile), profile_failures(profile)
    return SimpleNamespace(tokenizer=CharTokenizer(), observer=observer,
                           performer=performer, device=torch.device("cpu"),
                           profile=profile, tokenizer_json_sha256="0" * 64,
                           tokenizer_vocab_size=1000, model_output_dim=1000)


def _change_matmul_tf32(torch, pair):
    torch.backends.cuda.matmul.allow_tf32 = True
    return "matmul_allow_tf32"


def _change_cudnn_tf32(torch, pair):
    torch.backends.cudnn.allow_tf32 = True
    return "cudnn_allow_tf32"


def _change_precision(torch, pair):
    torch.set_float32_matmul_precision("high")
    return "float32_matmul_precision"


def _change_deterministic(torch, pair):
    torch.use_deterministic_algorithms(False)
    return "deterministic_algorithms"


def _change_attention(torch, pair):
    pair.observer.config._attn_implementation = "sdpa"
    return "attn_implementation"


@pytest.mark.parametrize("change", [
    _change_matmul_tf32, _change_cudnn_tf32, _change_precision,
    _change_deterministic, _change_attention])
def test_settings_change_between_load_and_scoring(numerics, monkeypatch, change):
    torch = numerics
    monkeypatch.setattr(torch.cuda, "is_initialized", lambda: False)
    loader.configure_numerics("cpu")
    pair = _loaded_cpu_pair(torch)
    field = change(torch, pair)
    ev = BinocularsAnalyzer(device="cpu").score_text(pair, "x" * 80)
    assert ev.result.value == "inconclusive"
    assert ev.reasons == [PROFILE_CHANGED]
    assert ev.raw_score is None and ev.score_direction is None
    # torch couples matmul allow_tf32 and float32 matmul precision, so changing
    # either one reports both
    assert field in ev.details["execution_profile_changes"]


def test_unchanged_settings_reach_scoring(numerics, monkeypatch):
    # Control for the test above: with no change, scoring is attempted (the
    # fake model raises, proving the pre-scoring check passed)
    torch = numerics
    monkeypatch.setattr(torch.cuda, "is_initialized", lambda: False)
    loader.configure_numerics("cpu")
    pair = _loaded_cpu_pair(torch)
    with pytest.raises(AssertionError, match="must not be run"):
        BinocularsAnalyzer(device="cpu").score_text(pair, "x" * 80)


def test_complete_cpu_profile_stays_uncalibrated(tmp_path):
    stats = {"nll_performer": 2.0, "xent": 2.5, "score": 0.8,
             "n_input_tokens": 100, "n_target_tokens": 99}
    window = {"tokens_total": 100, "tokens_scored": 100, "truncated": False,
              "scored_char_range": [0, 400]}
    ev = evidence_from_score(stats, window, CPU_PROFILE, None, "a" * 64, 151665,
                             151936, tmp_path / "none")
    assert ev.reasons == [NO_CALIBRATION]
    assert ev.details["execution_profile_complete"] is True
