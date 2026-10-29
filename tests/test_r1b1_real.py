"""R1-B1 real-model checks (slow; needs models/ and CUDA). Correctness only:
no timing or memory is measured or asserted here (feasibility is R1-B2)."""
import json
import math
import pathlib
import subprocess
import sys

import pytest
from binoculars_oracle import oracle

from litmus import config
from litmus.cli import main
from litmus.scorer.analyzer import NO_CALIBRATION, BinocularsAnalyzer
from litmus.scorer.binoculars import binoculars_statistics
from litmus.scorer.identity import SOURCE_FILES
from litmus.scorer.loader import (
    CUDA_ORDER_REASON,
    UNAVAILABLE,
    forward_logits,
    load_pair,
    profile_failures,
)
from litmus.scorer.tokenize import tokenize_window

pytestmark = pytest.mark.slow

ROOT = pathlib.Path(__file__).resolve().parent.parent

SENTENCES = [
    "The committee met on a grey morning to review the quarterly maintenance plan.",
    "Each department submitted a short list of repairs, ordered by cost and urgency.",
    "Several members asked whether the older pumps could last another winter.",
    "The engineer replied that the bearings were worn but the housings were sound.",
    "After a long discussion, the group agreed to replace two pumps in the spring.",
    "A smaller team will inspect the roof drains and report back within a month.",
    "Funding for the remaining items depends on the outcome of the annual audit.",
]
SHORT_TEXT = SENTENCES[0]
MEDIUM_TEXT = " ".join(SENTENCES * 2)
LONG_TEXT = " ".join(SENTENCES * 12)


@pytest.fixture(scope="module")
def pair():
    import torch
    assert torch.cuda.is_available(), "CUDA required for the R1-B1 slow suite"
    return load_pair(device="cuda")


@pytest.fixture(scope="module")
def analyzer(pair):
    a = BinocularsAnalyzer(device="cuda")
    a._pair = pair
    return a


def test_effective_settings_read_back(pair):
    import torch
    p = pair.profile
    print("\n[read-back profile]", json.dumps(p, indent=1))
    assert p["attn_implementation"] == "eager"
    assert pair.observer.config._attn_implementation == "eager"
    assert pair.performer.config._attn_implementation == "eager"
    assert p["matmul_allow_tf32"] is False and p["cudnn_allow_tf32"] is False
    assert p["float32_matmul_precision"] == "highest"
    assert p["deterministic_algorithms"] is True
    assert p["cublas_workspace_config"] == config.CUBLAS_WORKSPACE_CONFIG
    assert p["weight_dtype"] == "float32" and p["device_type"] == "cuda"
    assert UNAVAILABLE not in p.values()
    # Settings were applied before CUDA initialized in this process
    assert p["cuda_initialized_before_settings"] is False
    assert profile_failures(p, models=(("observer", pair.observer),
                                       ("performer", pair.performer))) == {}
    # Plain JSON types only (TorchVersion regression)
    assert all(type(v) in (str, bool, int) for v in p.values())
    assert p["torch_version"] == str(torch.__version__)
    assert not pair.observer.training and not pair.performer.training
    # Live state still matches what the profile recorded
    assert torch.backends.cuda.matmul.allow_tf32 is False
    assert torch.backends.cudnn.allow_tf32 is False
    assert pair.model_output_dim == 151936 and pair.tokenizer_vocab_size == 151665


def test_short_text_is_too_short(analyzer):
    ev = analyzer(SHORT_TEXT)
    assert ev.result.value == "inconclusive" and ev.reasons == ["too_short"]
    assert ev.raw_score is None
    assert ev.details["scored_window"]["tokens_scored"] < config.MIN_TOKENS


def test_medium_text_uncalibrated_evidence(analyzer):
    ev = analyzer(MEDIUM_TEXT)
    sw = ev.details["scored_window"]
    assert ev.result.value == "inconclusive" and ev.reasons == [NO_CALIBRATION]
    assert math.isfinite(ev.raw_score) and ev.raw_score > 0
    assert ev.score_direction == "lower_means_more_machine"
    assert ev.calibration is None
    assert config.MIN_TOKENS <= sw["tokens_scored"] == sw["tokens_total"] <= 512
    assert sw["truncated"] is False
    assert sw["scored_char_range"] == [0, len(MEDIUM_TEXT)]
    assert len(ev.details["scoring_config_hash"]) == 64
    assert ev.details["scoring_config"]["source_files"] == list(SOURCE_FILES) == [
        "src/litmus/config.py", "src/litmus/ingestion.py",
        "src/litmus/scorer/analyzer.py", "src/litmus/scorer/binoculars.py",
        "src/litmus/scorer/identity.py", "src/litmus/scorer/loader.py",
        "src/litmus/scorer/tokenize.py"]
    assert ev.details["execution_profile_complete"] is True
    assert ev.details["execution_profile_failures"] == {}


def test_long_text_truncates_to_512(analyzer, pair):
    ev = analyzer(LONG_TEXT)
    sw = ev.details["scored_window"]
    assert sw["truncated"] is True
    assert sw["tokens_scored"] == 512 and sw["tokens_total"] > 512
    end = sw["scored_char_range"][1]
    assert 0 < end < len(LONG_TEXT)
    # The window is exactly the first 512 tokens of the full tokenization,
    # and the scored character range covers exactly those tokens
    full = tokenize_window(pair.tokenizer, LONG_TEXT)
    prefix = tokenize_window(pair.tokenizer, LONG_TEXT[:end])
    assert prefix.ids == full.ids
    assert "only the first 512 tokens were scored" in ev.limitations


def test_scores_are_deterministic(analyzer):
    a, b = analyzer(MEDIUM_TEXT), analyzer(MEDIUM_TEXT)
    assert a.raw_score == b.raw_score
    assert a.details["scoring_config_hash"] == b.details["scoring_config_hash"]


def test_real_logits_slice_matches_oracle(pair):
    import torch
    window = tokenize_window(pair.tokenizer, MEDIUM_TEXT)
    obs = forward_logits(torch, pair.observer, window.ids, pair.device)
    perf = forward_logits(torch, pair.performer, window.ids, pair.device)
    n = 6  # rows of the full 151936-wide output, in pure Python
    ids = window.ids[:n]
    got = binoculars_statistics(obs[:n], perf[:n], torch.tensor(ids, device="cuda"))
    ref = oracle(obs[:n].cpu().tolist(), perf[:n].cpu().tolist(), ids)
    for key in ("nll_performer", "xent", "score"):
        assert math.isclose(got[key], ref[key], rel_tol=1e-5, abs_tol=1e-6), (
            key, got[key], ref[key])


def test_cli_binoculars_report_under_offline_guards(tmp_path, capsys):
    src = tmp_path / "synthetic.txt"
    src.write_text(MEDIUM_TEXT, encoding="utf-8")
    assert main(["analyze", str(src), "--text-origin", "binoculars",
                 "--device", "cuda"]) == 0
    rep = json.loads(capsys.readouterr().out)
    (origin,) = rep["segments"][0]["origin"]
    assert origin["method_id"] == "binoculars"
    assert origin["result"] == "inconclusive"
    assert origin["reasons"] == [NO_CALIBRATION]
    assert origin["calibration"] is None
    assert rep["offline"] == {"socket_guard": "loopback_only",
                              "subprocess_guard": "blocked"}
    # The reported configuration re-hashes to the reported scoring_config_hash
    from litmus.scorer.identity import scoring_config_hash
    details = origin["details"]
    reported = details["scoring_config_hash"]
    assert scoring_config_hash(details["scoring_config"]) == reported
    assert details["scoring_config"]["torch_version"] == "2.6.0+cu124"


# Fresh interpreters (tests only; analysis code never spawns processes). Tiny
# stand-in models: only the read-back profile is under test, not scoring.
ORDER_SCRIPT = r"""
import json, sys
from types import SimpleNamespace
import torch
from litmus.scorer import loader

def init_cuda():
    a = torch.ones(4, 4, device="cuda")
    (a @ a).sum().item()  # initializes CUDA and cuBLAS

class Stub:
    config = SimpleNamespace(_attn_implementation="eager")
    def parameters(self):
        yield torch.zeros(1)

assert not torch.cuda.is_initialized()
if sys.argv[1] == "init-first":
    init_cuda()
loader.configure_numerics("cuda")
if sys.argv[1] == "configure-first":
    init_cuda()
profile = loader.read_profile(torch, torch.device("cuda"), Stub(), Stub())
print(json.dumps({"cuda_initialized_now": torch.cuda.is_initialized(),
                  "profile": profile,
                  "failures": loader.profile_failures(profile)}))
"""


def _run_order(order):
    proc = subprocess.run([sys.executable, "-c", ORDER_SCRIPT, order],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    print(f"\n[{order}]", json.dumps(out, indent=1))
    assert out["cuda_initialized_now"] is True
    return out


def test_configure_then_initialize_cuda_is_complete():
    out = _run_order("configure-first")
    assert out["profile"]["cuda_initialized_before_settings"] is False
    assert out["failures"] == {}


def test_initialize_cuda_then_configure_is_incomplete():
    out = _run_order("init-first")
    assert out["profile"]["cuda_initialized_before_settings"] is True
    assert out["failures"] == {"cuda_initialized_before_settings": CUDA_ORDER_REASON}