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
def test_unapproved_redirect_refused(url, tmp_path):
    with pytest.raises(PrepError, match="unapproved_redirect_host"):
        ArtifactRedirect(Budget(tmp_path)).redirect_request(
            None, None, 302, "", {}, url
        )


class ResponseBody(io.BytesIO):
    def __init__(self, content, fail=False):
        super().__init__(content)
        self.received = 0
        self.fail = fail

    def read(self, count=-1):
        assert count >= 0, "unbounded response-body read"
        if self.fail:
            raise OSError("constructed body interruption")
        block = super().read(count)
        self.received += len(block)
        return block


def offline_opener(monkeypatch, budget, responses):
    import socket
    import urllib.request
    from email.message import Message
    from urllib.response import addinfourl

    from litmus.data_prep import acquisition

    def forbidden(*args, **kwargs):
        pytest.fail("unexpected network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    opened = []

    class HTTPS(urllib.request.HTTPSHandler):
        def https_open(self, request):
            opened.append(request.full_url)
            status, body, location = responses[len(opened) - 1]
            headers = Message()
            if location:
                headers["Location"] = location
            response = addinfourl(body, headers, request.full_url, status)
            response.msg = "constructed"
            return response

    opener = urllib.request.build_opener(
        HTTPS(), ArtifactRedirect(budget), acquisition.BudgetHTTPErrorHandler(budget)
    )
    return opener, opened


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_body_uses_budget_before_final_response(tmp_path, monkeypatch, status):
    budget = Budget(tmp_path, transfer_limit=2_000_000)
    redirect = ResponseBody(b"redirect body")
    final = ResponseBody(b"accepted")
    opener, opened = offline_opener(
        monkeypatch,
        budget,
        [
            (status, redirect, "https://us.aws.cdn.hf.co/final"),
            (200, final, None),
        ],
    )
    with opener.open("https://huggingface.co/pinned", timeout=1) as response:
        assert budget.read(response, 8) == b"accepted"
    assert len(opened) == 2
    assert redirect.closed and final.closed
    assert redirect.received == 13 and final.received == 8
    assert budget.state["received_bytes"] == 21
    resumed = Budget(tmp_path, transfer_limit=2_000_000)
    assert resumed.state == budget.state
    assert 21 <= resumed.state["charged_bytes"] <= resumed.limit


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503])
def test_http_error_body_uses_budget_and_closes(tmp_path, monkeypatch, status):
    budget = Budget(tmp_path, transfer_limit=2_000_000)
    body = ResponseBody(b"private error body")
    opener, opened = offline_opener(monkeypatch, budget, [(status, body, None)])
    with pytest.raises(PrepError, match=f"http_response_error:{status}") as error:
        opener.open("https://huggingface.co/pinned", timeout=1)
    assert "private error body" not in str(error.value)
    assert body.closed and body.received == 18 and len(opened) == 1
    assert budget.state["received_bytes"] == 18
    assert Budget(tmp_path, transfer_limit=2_000_000).state == budget.state


@pytest.mark.parametrize("status", [302, 500])
def test_intermediate_body_cannot_exceed_budget_or_follow(
    tmp_path, monkeypatch, status
):
    budget = Budget(tmp_path, transfer_limit=10)
    body = ResponseBody(b"0123456789unread")
    opener, opened = offline_opener(
        monkeypatch,
        budget,
        [
            (status, body, "https://us.aws.cdn.hf.co/final"),
        ],
    )
    with pytest.raises(PrepError, match="transfer_budget_exceeded"):
        opener.open("https://huggingface.co/pinned", timeout=1)
    assert len(opened) == 1 and body.closed and body.received == 10
    assert budget.state == {"charged_bytes": 10, "received_bytes": 10}


@pytest.mark.parametrize("status", [302, 500])
def test_intermediate_read_failure_keeps_reservation_and_closes(
    tmp_path, monkeypatch, status
):
    budget = Budget(tmp_path, transfer_limit=10)
    body = ResponseBody(b"unused", fail=True)
    opener, opened = offline_opener(
        monkeypatch,
        budget,
        [
            (status, body, "https://us.aws.cdn.hf.co/final"),
        ],
    )
    with pytest.raises(OSError, match="constructed body interruption"):
        opener.open("https://huggingface.co/pinned", timeout=1)
    assert len(opened) == 1 and body.closed
    assert Budget(tmp_path, transfer_limit=10).state == {
        "charged_bytes": 10,
        "received_bytes": 0,
    }


def test_redirect_chain_then_error_all_bodies_share_budget(tmp_path, monkeypatch):
    budget = Budget(tmp_path, transfer_limit=2_000_000)
    bodies = [ResponseBody(b"first"), ResponseBody(b"second"), ResponseBody(b"error")]
    opener, opened = offline_opener(
        monkeypatch,
        budget,
        [
            (302, bodies[0], "https://huggingface.co/second"),
            (307, bodies[1], "https://us.aws.cdn.hf.co/error"),
            (503, bodies[2], None),
        ],
    )
    with pytest.raises(PrepError, match="http_response_error:503"):
        opener.open("https://huggingface.co/pinned", timeout=1)
    assert len(opened) == 3 and all(b.closed for b in bodies)
    assert budget.state["received_bytes"] == sum(b.received for b in bodies) == 16


def test_previous_payload_reduces_intermediate_body_allowance(tmp_path, monkeypatch):
    budget = Budget(tmp_path, transfer_limit=10)
    assert budget.read(io.BytesIO(b"prior!"), 6) == b"prior!"
    body = ResponseBody(b"0123456789")
    opener, opened = offline_opener(
        monkeypatch, budget, [(302, body, "https://huggingface.co/final")]
    )
    with pytest.raises(PrepError, match="transfer_budget_exceeded"):
        opener.open("https://huggingface.co/pinned", timeout=1)
    assert len(opened) == 1 and body.closed and body.received == 4
    assert budget.state == {"charged_bytes": 10, "received_bytes": 10}


@pytest.mark.parametrize("location", [None, "https://evil.example/unapproved"])
def test_invalid_redirect_closes_budgeted_body_without_following(
    tmp_path, monkeypatch, location
):
    budget = Budget(tmp_path, transfer_limit=2_000_000)
    body = ResponseBody(b"redirect body")
    opener, opened = offline_opener(monkeypatch, budget, [(302, body, location)])
    with pytest.raises(
        PrepError, match="redirect_location_missing|unapproved_redirect_host"
    ):
        opener.open("https://huggingface.co/pinned", timeout=1)
    assert len(opened) == 1 and body.closed and body.received == 13
    assert budget.state["received_bytes"] == 13
