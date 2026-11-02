"""Constructed access fixtures; no real held-out blob reads."""

import socket

import pytest

from litmus.calibration_run import scoring_guards
from litmus.evaluation.gate import Access, check_hashes
from litmus.evaluation.gate import test_projection as project_test
from litmus.scorer.calibration import CalibrationError, sha


def test_no_log_read_denied_and_single_open_token(tmp_path):
    blob = tmp_path / "data/raid/prepared/primary/texts/x.txt"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"constructed")
    row = {
        "id": "x",
        "split": "test",
        "text_blob": "texts/x.txt",
        "raw_text_sha256": sha(b"constructed"),
    }
    with Access(tmp_path, [row]) as access:
        with pytest.raises(CalibrationError):
            blob.read_bytes()
        access.authorize(row, durable=True)
        assert blob.read_bytes() == b"constructed"
        with pytest.raises(CalibrationError):
            blob.read_bytes()
        with pytest.raises(CalibrationError):
            socket.getaddrinfo("localhost", 80)
    assert access.opens == 1 and access.blocked == 3


@pytest.mark.parametrize("bad", ["../escape", "texts/../x", "texts/x.txt"])
def test_path_and_hash_filename_injection(tmp_path, bad):
    with pytest.raises(CalibrationError):
        with Access(
            tmp_path,
            [{"id": "x", "split": "dev", "text_blob": bad, "raw_text_sha256": "x"}],
        ):
            pass


def test_frozen_hash_failure_before_any_read(tmp_path):
    p = tmp_path / "source.py"
    p.write_bytes(b"old")
    check_hashes(tmp_path, {"source.py": sha(b"old")})
    p.write_bytes(b"changed")
    with pytest.raises(CalibrationError):
        check_hashes(tmp_path, {"source.py": sha(b"old")})


def test_projection_rejects_duplicate_and_dev_only():
    with pytest.raises(CalibrationError):
        project_test([{"id": "x", "split": "test"}] * 2)
    with pytest.raises(CalibrationError):
        project_test([{"id": "x", "split": "dev"}])


def test_original_f_guard_is_still_dev_only(tmp_path):
    with pytest.raises(CalibrationError, match="test_row"):
        with scoring_guards(tmp_path, [{"split": "test", "text_blob": "texts/x"}]):
            pass
