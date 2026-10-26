"""Integration (slow, local only): real pinned 0.5B pair on CPU fp32 (SPEC §8.1). Loads models; never in default CI."""
import json
from pathlib import Path

import pytest

from litmus.scoring import load_pair, score_texts

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-6  # absolute, per statistic, vs the committed CPU fp32 drift run and between repeats
TEXT_IDS = ["d01", "d16"]  # 74 tokens; 550 tokens truncated to 512


@pytest.fixture(scope="module")
def pair():
    return load_pair("0.5b", device="cpu", dtype="float32")


def test_cpu_fp32_matches_drift_run_and_repeats(pair):
    texts = {t["id"]: t["text"] for t in json.loads((ROOT / "eval/fixtures/drift_texts.json").read_bytes())["texts"]}
    drift = json.loads((ROOT / "eval/results/runtime_drift.json").read_bytes())
    reference = next(r for r in drift["runs"] if r["config"] == "cpu_fp32" and r["repeat"] == 0)

    first = score_texts([texts[t] for t in TEXT_IDS], pair)
    second = score_texts([texts[t] for t in TEXT_IDS], pair)
    for tid, a, b in zip(TEXT_IDS, first, second):
        expected = reference["texts"][tid]
        assert a.status == "ok"
        assert a.n_input_tokens == drift["inputs"][tid]["n_input_tokens"]
        assert a.truncated == drift["inputs"][tid]["truncated"]
        for key in ["nll_performer", "nll_observer", "xent", "score"]:
            assert abs(getattr(a, key) - expected[key]) <= TOLERANCE, (tid, key, getattr(a, key), expected[key])
            assert abs(getattr(a, key) - getattr(b, key)) <= TOLERANCE


def test_too_short_real_text(pair):
    result = score_texts(["Too short to score."], pair)[0]
    assert result.status == "too_short" and result.score is None
