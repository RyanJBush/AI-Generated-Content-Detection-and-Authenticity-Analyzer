"""Model-free tests for litmus.identity hashing."""
import dataclasses
import subprocess

import pytest
from fakes import fake_pair

import litmus.identity as identity_module
from litmus.identity import (
    _normalized_file_sha256,
    canonical_json,
    compute_identity,
    sha256_hex,
)


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": [1, "é"]}) == canonical_json({"a": [1, "é"], "b": 1})
    assert canonical_json({"a": "é"}) == '{"a":"é"}'.encode()


def test_hashes_are_deterministic_and_combined():
    first, second = compute_identity(fake_pair()), compute_identity(fake_pair())
    for key in ["scoring_identity_hash", "execution_profile_hash", "scoring_config_hash"]:
        assert first[key] == second[key]
        assert len(first[key]) == 64
    assert first["scoring_config_hash"] == sha256_hex(canonical_json({
        "scoring_identity_hash": first["scoring_identity_hash"],
        "execution_profile_hash": first["execution_profile_hash"],
    }))


def test_weight_dtype_changes_profile_but_not_scoring_identity():
    base = compute_identity(fake_pair())
    other = compute_identity(dataclasses.replace(fake_pair(), weight_dtype="bfloat16"))
    assert other["scoring_identity_hash"] == base["scoring_identity_hash"]
    assert other["execution_profile_hash"] != base["execution_profile_hash"]
    assert other["scoring_config_hash"] != base["scoring_config_hash"]


def test_model_revision_changes_scoring_identity():
    base = compute_identity(fake_pair())
    other = compute_identity(dataclasses.replace(fake_pair(), performer_id="fake/performer@1"))
    assert other["scoring_identity_hash"] != base["scoring_identity_hash"]


def test_environment_is_not_hashed():
    identity = compute_identity(fake_pair())
    assert "environment" not in identity["scoring_identity"]
    assert "platform" not in identity["execution_profile"]


def test_file_hash_ignores_line_endings(tmp_path):
    lf, crlf = tmp_path / "lf.txt", tmp_path / "crlf.txt"
    lf.write_bytes(b"a\nb\n")
    crlf.write_bytes(b"a\r\nb\r\n")
    assert _normalized_file_sha256(lf) == _normalized_file_sha256(crlf)


# --- Optional NVIDIA driver metadata (never hashed, never fatal) ---------------------------------------------


def cuda_pair(monkeypatch):
    monkeypatch.setattr(identity_module.torch.cuda, "get_device_name", lambda index: "Fake GPU")
    return dataclasses.replace(fake_pair(), device="cuda")


def fake_run(result=None, exc=None):
    def run(command, check, capture_output, text, timeout):
        assert check is False
        assert command == ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]
        assert timeout == identity_module.NVIDIA_SMI_TIMEOUT_SECONDS
        if exc is not None:
            raise exc
        return result
    return run


FAILURES = {
    "not_found": (fake_run(exc=FileNotFoundError("nvidia-smi")), "nvidia-smi not found"),
    "timeout": (fake_run(exc=subprocess.TimeoutExpired("nvidia-smi", 5)), "nvidia-smi timed out after 5 s"),
    "nonzero_exit": (
        fake_run(subprocess.CompletedProcess([], 9, stdout="", stderr="NVIDIA-SMI has failed\n")),
        "nvidia-smi exited with code 9: NVIDIA-SMI has failed",
    ),
    "unparseable": (
        fake_run(subprocess.CompletedProcess([], 0, stdout="[N/A]\n", stderr="")),
        "unparseable nvidia-smi output: '[N/A]'",
    ),
    "empty_output": (fake_run(subprocess.CompletedProcess([], 0, stdout="\n", stderr="")),
                     "unparseable nvidia-smi output: ''"),
}


@pytest.mark.parametrize("case", sorted(FAILURES))
def test_driver_lookup_failures_record_null_and_reason(monkeypatch, case):
    run, reason = FAILURES[case]
    monkeypatch.setattr(identity_module.subprocess, "run", run)
    environment = compute_identity(cuda_pair(monkeypatch))["environment"]
    assert environment["nvidia_driver_version"] is None
    assert environment["nvidia_driver_version_reason"] == reason
    assert environment["torch_cuda_runtime"] == identity_module.torch.version.cuda


def test_driver_lookup_success(monkeypatch):
    monkeypatch.setattr(identity_module.subprocess, "run",
                        fake_run(subprocess.CompletedProcess([], 0, stdout="572.60\n", stderr="")))
    environment = compute_identity(cuda_pair(monkeypatch))["environment"]
    assert environment["nvidia_driver_version"] == "572.60"
    assert environment["nvidia_driver_version_reason"] is None


def test_driver_metadata_never_changes_hashes(monkeypatch):
    def hashes(run):
        monkeypatch.setattr(identity_module.subprocess, "run", run)
        identity = compute_identity(cuda_pair(monkeypatch))
        return {k: identity[k] for k in ["scoring_identity_hash", "execution_profile_hash", "scoring_config_hash"]}

    reference = hashes(fake_run(subprocess.CompletedProcess([], 0, stdout="572.60\n", stderr="")))
    assert hashes(fake_run(subprocess.CompletedProcess([], 0, stdout="999.99\n", stderr=""))) == reference
    for run, _ in FAILURES.values():
        assert hashes(run) == reference
    identity = compute_identity(cuda_pair(monkeypatch))
    for section in ["scoring_identity", "execution_profile"]:
        assert not any("driver" in key for key in identity[section])


def test_cpu_device_does_not_query_driver(monkeypatch):
    def run(*args, **kwargs):
        raise AssertionError("nvidia-smi must not be called for a CPU profile")
    monkeypatch.setattr(identity_module.subprocess, "run", run)
    environment = compute_identity(fake_pair())["environment"]
    assert environment["nvidia_driver_version"] is None
    assert environment["nvidia_driver_version_reason"] == "not queried: device is cpu"
