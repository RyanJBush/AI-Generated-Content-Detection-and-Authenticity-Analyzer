"""Network-free acquisition guards and cumulative budget accounting."""

import io
import json

import pytest

from litmus.data_prep.acquisition import (
    ArtifactRedirect,
    Budget,
    PrepError,
    validate_metadata,
)


def metadata():
    from litmus.data_prep.acquisition import REVISION, SHA256, SIZE

    return {
        "sha": REVISION,
        "siblings": [
            {
                "rfilename": "train.csv",
                "size": SIZE,
                "lfs": {"sha256": SHA256, "size": SIZE},
            }
        ],
    }


def test_revision_specific_identity():
    assert validate_metadata(metadata())["path"] == "train.csv"
    for field in ("sha", "size", "sha256"):
        value = metadata()
        if field == "sha":
            value[field] = "different"
        elif field == "size":
            value["siblings"][0]["lfs"][field] = 1
        else:
            value["siblings"][0]["lfs"][field] = "wrong"
        with pytest.raises(PrepError):
            validate_metadata(value)


def test_budget_is_durable_and_never_reads_beyond_limit(tmp_path):
    budget = Budget(tmp_path, transfer_limit=10, artifact_limit=100000)
    stream = io.BytesIO(b"0123456789more")
    assert budget.read(stream, 8) == b"01234567"
    again = Budget(tmp_path, transfer_limit=10, artifact_limit=100000)
    assert again.read(stream, 8) == b"89"
    with pytest.raises(PrepError):
        again.read(stream, 1)
    assert stream.tell() == 10
    saved = json.loads((tmp_path / "transfer.json").read_text())
    assert saved["charged_bytes"] == saved["received_bytes"] == 10


def test_storage_and_metadata_fail_closed(tmp_path):
    (tmp_path / "existing.part").write_bytes(b"a" * 100)
    with pytest.raises(PrepError):
        Budget(tmp_path, artifact_limit=10).check_storage()
    with pytest.raises(PrepError):
        validate_metadata({"sha": "wrong", "siblings": []})


def test_failed_read_reservation_is_not_forgotten(tmp_path):
    class Broken:
        def read(self, count):
            raise OSError("constructed transport interruption")

    budget = Budget(tmp_path, transfer_limit=10, artifact_limit=100000)
    with pytest.raises(OSError):
        budget.read(Broken(), 8)
    again = Budget(tmp_path, transfer_limit=10, artifact_limit=100000)
    assert again.state["charged_bytes"] == 8
    assert again.state["received_bytes"] == 0
    assert again.read(io.BytesIO(b"12345678"), 8) == b"12"
    with pytest.raises(PrepError):
        again.read(io.BytesIO(b"3"), 1)


@pytest.mark.parametrize(
    "url", ["http://huggingface.co/file", "https://evil.example/x"]
)
def test_unapproved_redirect_refused(url):
    with pytest.raises(PrepError, match="unapproved_redirect_host"):
        ArtifactRedirect().redirect_request(None, None, 302, "", {}, url)
