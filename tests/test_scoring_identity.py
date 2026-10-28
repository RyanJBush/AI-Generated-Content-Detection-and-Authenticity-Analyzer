"""scoring_config_hash, source identity, and strict calibration matching (R1-B1)."""
import json

import pytest

from litmus import config
from litmus.scorer import identity
from litmus.scorer.analyzer import (
    CALIBRATION_NOT_APPLIED,
    NO_CALIBRATION,
    PROFILE_INCOMPLETE,
    calibration_reason,
    evidence_from_score,
)
from litmus.scorer.calibration import find_calibration
from litmus.scorer.loader import UNAVAILABLE, profile_is_complete

# A fixed, fully specified profile (test input, not a measurement)
PROFILE = {
    "device_type": "cuda",
    "gpu_name": "Test GPU",
    "nvidia_driver_version": "1.2",
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
}
SOURCE_HASH = "0" * 64
STATIC = identity.static_fields()


def fields(profile=PROFILE, static=STATIC, files=identity.SOURCE_FILES,
           src=SOURCE_HASH):
    return identity.config_fields(dict(profile), dict(static), list(files), src)


# Golden digest for the fixed inputs above, cross-checked with `sha256sum` over
# the canonical JSON text. Recompute deliberately (and record why) only when the
# field set or a static configuration value changes.
GOLDEN_HASH = "51a2bf595030b334a7ad12b6b65335f363eadd51e36e0cd0913f5e41240cfce6"


def test_to_json_keeps_str_subclasses_as_text():
    # Regression: torch.__version__ is a str subclass with a __dict__ and was
    # serialized as {} in an R1-B1 draft report
    from litmus.schemas import to_json

    class Version(str):
        def __init__(self, value):
            self.extra = "x"

    v = Version("2.6.0+cu124")
    assert v.__dict__ == {"extra": "x"}
    assert to_json({"torch_version": v}) == {"torch_version": "2.6.0+cu124"}
    assert type(to_json(v)) is str


def test_field_set_is_exactly_documented():
    f = fields()
    expected = (set(identity.STATIC_FIELDS) | set(identity.PROFILE_FIELDS)
                | set(identity.SOURCE_FIELDS))
    assert set(f) == expected


def test_canonical_json_format():
    assert identity.canonical_json({"b": 1, "a": [True, None, "é"]}) == (
        '{"a":[true,null,"é"],"b":1}'.encode("utf-8"))


def test_golden_hash():
    assert identity.scoring_config_hash(fields()) == GOLDEN_HASH


def _variants():
    """One single-field change per hashed field."""
    base = fields()
    for name, value in base.items():
        if isinstance(value, bool):
            new = not value
        elif isinstance(value, int):
            new = value + 1
        elif isinstance(value, list):
            new = value[:-1]
        else:
            new = value + "-changed"
        yield name, new


@pytest.mark.parametrize("name, new", list(_variants()))
def test_hash_changes_when_any_single_field_changes(name, new):
    base = fields()
    changed = dict(base, **{name: new})
    assert identity.scoring_config_hash(changed) != identity.scoring_config_hash(base)


def test_every_field_is_covered_by_the_variants():
    assert {n for n, _ in _variants()} == set(fields())


def test_profile_disagreeing_with_configuration_is_rejected():
    with pytest.raises(ValueError, match="weight_dtype"):
        fields(profile=dict(PROFILE, weight_dtype="bfloat16"))


def test_crlf_and_lf_source_hash_equal(tmp_path):
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    for d in (lf, crlf):
        (d / "src").mkdir(parents=True)
    (lf / "src" / "a.py").write_bytes(b"x = 1\ny = 2\n")
    (crlf / "src" / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    assert (identity.source_sha256(["src/a.py"], lf)
            == identity.source_sha256(["src/a.py"], crlf))
    (crlf / "src" / "a.py").write_bytes(b"x = 1\r\ny = 3\r\n")
    assert (identity.source_sha256(["src/a.py"], lf)
            != identity.source_sha256(["src/a.py"], crlf))


def test_source_hash_depends_on_file_list(tmp_path):
    (tmp_path / "a.py").write_bytes(b"a\n")
    (tmp_path / "b.py").write_bytes(b"b\n")
    assert (identity.source_sha256(["a.py"], tmp_path)
            != identity.source_sha256(["a.py", "b.py"], tmp_path))
    # Order of the list does not matter (sorted), content and names do
    assert (identity.source_sha256(["b.py", "a.py"], tmp_path)
            == identity.source_sha256(["a.py", "b.py"], tmp_path))


def test_real_source_files_exist_and_hash():
    digest = identity.source_sha256()
    assert len(digest) == 64
    assert "src/litmus/scorer/binoculars.py" in identity.SOURCE_FILES


# --- incomplete profile (CA2) and strict calibration lookup ---

def _write_calibration(directory, config_hash):
    directory.mkdir(exist_ok=True)
    (directory / "cal.json").write_text(json.dumps({
        "scoring_config_hash": config_hash, "threshold_c": 0.9, "alpha": 0.05,
    }), encoding="utf-8")


def test_incomplete_profile_is_reported_and_never_matches(tmp_path):
    incomplete = dict(PROFILE, nvidia_driver_version=UNAVAILABLE)
    assert profile_is_complete(PROFILE)
    assert not profile_is_complete(incomplete)
    h = identity.scoring_config_hash(fields(profile=incomplete))
    # Even a calibration carrying this exact hash is never used
    _write_calibration(tmp_path / "cals", h)
    assert find_calibration(h, tmp_path / "cals") is not None
    assert calibration_reason(incomplete, h, tmp_path / "cals") == PROFILE_INCOMPLETE


def test_mismatching_calibration_hash_is_inconclusive(tmp_path):
    h = identity.scoring_config_hash(fields())
    _write_calibration(tmp_path / "cals", "f" * 64)
    assert find_calibration(h, tmp_path / "cals") is None
    assert calibration_reason(PROFILE, h, tmp_path / "cals") == NO_CALIBRATION


def test_no_calibrations_directory_is_inconclusive(tmp_path):
    h = identity.scoring_config_hash(fields())
    assert calibration_reason(PROFILE, h, tmp_path / "missing") == NO_CALIBRATION


def test_matching_calibration_is_not_applied_in_r1b1(tmp_path):
    h = identity.scoring_config_hash(fields())
    _write_calibration(tmp_path / "cals", h)
    assert calibration_reason(PROFILE, h, tmp_path / "cals") == CALIBRATION_NOT_APPLIED


def test_cpu_runs_are_always_uncalibrated(tmp_path):
    cpu = dict(PROFILE, device_type="cpu", gpu_name="not_applicable",
               nvidia_driver_version="not_applicable", cuda_runtime="not_applicable")
    h = identity.scoring_config_hash(fields(profile=cpu))
    _write_calibration(tmp_path / "cals", h)  # even an exact match
    assert profile_is_complete(cpu)
    assert calibration_reason(cpu, h, tmp_path / "cals") == NO_CALIBRATION


@pytest.mark.parametrize("profile, reason", [
    (PROFILE, NO_CALIBRATION),
    (dict(PROFILE, gpu_name=UNAVAILABLE), PROFILE_INCOMPLETE),
])
def test_evidence_is_uncalibrated_and_inconclusive(tmp_path, profile, reason):
    f = fields(profile=profile)
    h = identity.scoring_config_hash(f)
    stats = {"nll_performer": 2.0, "xent": 2.5, "score": 0.8,
             "n_input_tokens": 100, "n_target_tokens": 99}
    window = {"tokens_total": 100, "tokens_scored": 100, "truncated": False,
              "scored_char_range": [0, 400]}
    ev = evidence_from_score(stats, window, profile, f, h, 151665, 151936,
                             tmp_path / "none")
    assert ev.result.value == "inconclusive"
    assert ev.reasons == [reason]
    assert ev.raw_score == 0.8
    assert ev.score_direction == config.SCORE_DIRECTION == "lower_means_more_machine"
    assert ev.calibration is None
    assert ev.details["scoring_config_hash"] == h
    assert ev.details["scored_window"] == window
    assert ev.details["execution_profile_complete"] is (reason == NO_CALIBRATION)
    assert ev.limitations
