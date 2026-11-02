"""scoring_config_hash, source identity, and strict calibration matching (R1-B1)."""

import json

import pytest

from litmus import config
from litmus.scorer import identity
from litmus.scorer.analyzer import (
    CALIBRATION_APPLIED,
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
    "cuda_initialized_before_settings": False,
}
SOURCE_HASH = "0" * 64
STATIC = identity.static_fields()


def fields(
    profile=PROFILE, static=STATIC, files=identity.SOURCE_FILES, src=SOURCE_HASH
):
    return identity.config_fields(dict(profile), dict(static), list(files), src)


# Golden digest for the fixed inputs above, cross-checked with `sha256sum` over
# the canonical JSON text. Recompute deliberately (and record why) only when the
# field set or a static configuration value changes.
# R1-B1 corrections: recomputed because the field set gained
# cuda_initialized_before_settings and source_files gained analyzer.py and
# identity.py (was 51a2bf595030b334a7ad12b6b65335f363eadd51e36e0cd0913f5e41240cfce6).
# R1-F: source_files now includes calibration_run.py and calibration.py.
# Independent stdlib JSON/SHA-256 oracle for the same fixed inputs gives:
GOLDEN_HASH = "ec253feddd087221252a4a6d2b9498e311800fe966b0fb0c7e15231a3a6edda8"


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
    expected = (
        set(identity.STATIC_FIELDS)
        | set(identity.PROFILE_FIELDS)
        | set(identity.SOURCE_FIELDS)
    )
    assert set(f) == expected


def test_canonical_json_format():
    assert identity.canonical_json({"b": 1, "a": [True, None, "\u00e9"]}) == (
        '{"a":[true,null,"\u00e9"],"b":1}'.encode("utf-8")
    )


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
    assert identity.source_sha256(["src/a.py"], lf) == identity.source_sha256(
        ["src/a.py"], crlf
    )
    (crlf / "src" / "a.py").write_bytes(b"x = 1\r\ny = 3\r\n")
    assert identity.source_sha256(["src/a.py"], lf) != identity.source_sha256(
        ["src/a.py"], crlf
    )


def test_source_hash_depends_on_file_list(tmp_path):
    (tmp_path / "a.py").write_bytes(b"a\n")
    (tmp_path / "b.py").write_bytes(b"b\n")
    assert identity.source_sha256(["a.py"], tmp_path) != identity.source_sha256(
        ["a.py", "b.py"], tmp_path
    )
    # Order of the list does not matter (sorted), content and names do
    assert identity.source_sha256(["b.py", "a.py"], tmp_path) == identity.source_sha256(
        ["a.py", "b.py"], tmp_path
    )


def test_real_source_files_exist_and_hash():
    digest = identity.source_sha256()
    assert len(digest) == 64
    assert "src/litmus/scorer/binoculars.py" in identity.SOURCE_FILES


# --- incomplete profile (CA2) and strict calibration lookup ---


def _write_calibration(directory, config_fields=None):
    from litmus.scorer.calibration import create_artifact

    directory.mkdir(exist_ok=True)
    value = create_artifact(
        [1.0] * 200,
        config_fields or fields(),
        {
            "dev_set_id": "1" * 64,
            "prepared_manifest_sha256": "2" * 64,
            "reconciliation_sha256": "3" * 64,
            "scores_sha256": "4" * 64,
            "source_run_id": "constructed",
            "failed_negatives": 0,
        },
        "2026-11-01T00:00:00+00:00",
    )
    (directory / "cal.json").write_text(json.dumps(value), encoding="utf-8")
    return value


def test_incomplete_profile_is_reported_and_never_matches(tmp_path):
    incomplete = dict(PROFILE, nvidia_driver_version=UNAVAILABLE)
    assert profile_is_complete(PROFILE)
    assert not profile_is_complete(incomplete)
    h = identity.scoring_config_hash(fields(profile=incomplete))
    _write_calibration(tmp_path / "cals")
    assert calibration_reason(incomplete, h, tmp_path / "cals") == PROFILE_INCOMPLETE


def test_mismatching_calibration_hash_is_inconclusive(tmp_path):
    h = identity.scoring_config_hash(fields())
    other = fields(static=dict(STATIC, scorer_version="constructed-other"))
    _write_calibration(tmp_path / "cals", other)
    assert find_calibration(h, tmp_path / "cals") is None
    assert calibration_reason(PROFILE, h, tmp_path / "cals") == NO_CALIBRATION


def test_no_calibrations_directory_is_inconclusive(tmp_path):
    h = identity.scoring_config_hash(fields())
    assert calibration_reason(PROFILE, h, tmp_path / "missing") == NO_CALIBRATION


def test_matching_validated_calibration_is_applied(tmp_path):
    h = identity.scoring_config_hash(fields())
    _write_calibration(tmp_path / "cals")
    assert calibration_reason(PROFILE, h, tmp_path / "cals") == CALIBRATION_APPLIED


def test_cpu_runs_are_always_uncalibrated(tmp_path):
    cpu = dict(
        PROFILE,
        device_type="cpu",
        gpu_name="not_applicable",
        nvidia_driver_version="not_applicable",
        cuda_runtime="not_applicable",
        cublas_workspace_config="not_applicable",
    )
    h = identity.scoring_config_hash(fields(profile=cpu))
    _write_calibration(tmp_path / "cals")
    assert profile_is_complete(cpu)
    assert calibration_reason(cpu, h, tmp_path / "cals") == NO_CALIBRATION


@pytest.mark.parametrize(
    "profile, reason",
    [
        (PROFILE, NO_CALIBRATION),
        (dict(PROFILE, gpu_name=UNAVAILABLE), PROFILE_INCOMPLETE),
    ],
)
def test_evidence_is_uncalibrated_and_inconclusive(tmp_path, profile, reason):
    f = fields(profile=profile)
    h = identity.scoring_config_hash(f)
    stats = {
        "nll_performer": 2.0,
        "xent": 2.5,
        "score": 0.8,
        "n_input_tokens": 100,
        "n_target_tokens": 99,
    }
    window = {
        "tokens_total": 100,
        "tokens_scored": 100,
        "truncated": False,
        "scored_char_range": [0, 400],
    }
    ev = evidence_from_score(
        stats, window, profile, f, h, 151665, 151936, tmp_path / "none"
    )
    assert ev.result.value == "inconclusive"
    assert ev.reasons == [reason]
    assert ev.raw_score == 0.8
    assert ev.score_direction == config.SCORE_DIRECTION == "lower_means_more_machine"
    assert ev.calibration is None
    assert ev.details["scoring_config_hash"] == h
    assert ev.details["scored_window"] == window
    assert ev.details["execution_profile_complete"] is (reason == NO_CALIBRATION)
    assert ev.limitations


# --- source identity over the full list (R1-B1 corrections Fix 2) ---


def _copy_sources(root, newline=b"\n"):
    for rel in identity.SOURCE_FILES:
        data = (identity._SRC_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data.replace(b"\n", newline))


def test_source_list_includes_analyzer_and_identity():
    assert "src/litmus/scorer/analyzer.py" in identity.SOURCE_FILES
    assert "src/litmus/scorer/identity.py" in identity.SOURCE_FILES
    assert len(set(identity.SOURCE_FILES)) == len(identity.SOURCE_FILES) == 9


@pytest.mark.parametrize("rel", identity.SOURCE_FILES)
def test_changing_any_listed_file_changes_both_hashes(tmp_path, rel):
    _copy_sources(tmp_path)
    before = identity.source_sha256(root=tmp_path)
    # The copy is the real source, so the injected root reproduces the real hash
    assert before == identity.source_sha256()
    target = tmp_path / rel
    target.write_bytes(target.read_bytes() + b"# changed\n")
    after = identity.source_sha256(root=tmp_path)
    assert after != before
    assert identity.scoring_config_hash(
        fields(src=after)
    ) != identity.scoring_config_hash(fields(src=before))


def test_crlf_and_lf_copies_of_the_full_list_hash_equal(tmp_path):
    _copy_sources(tmp_path / "lf", b"\n")
    _copy_sources(tmp_path / "crlf", b"\r\n")
    assert (
        identity.source_sha256(root=tmp_path / "lf")
        == identity.source_sha256(root=tmp_path / "crlf")
        == identity.source_sha256()
    )
