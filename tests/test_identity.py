"""Model-free tests for litmus.identity hashing."""
import dataclasses

from fakes import fake_pair

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
