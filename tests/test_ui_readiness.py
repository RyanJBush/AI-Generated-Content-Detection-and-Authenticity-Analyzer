"""Real HTTP regressions for upload bounds and safe error/display handling."""

import http.client
import json
import socket
import threading
import time

import pytest

from litmus.local_ui import server as module


@pytest.fixture
def server():
    app = module.make_server(0)
    thread = threading.Thread(
        target=app.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield app
    app.shutdown()
    app.server_close()
    app.service.close()
    thread.join(3)


def upload(app, filename, data=b"sample"):
    c = http.client.HTTPConnection(*app.server_address, timeout=2)
    c.request(
        "POST",
        "/api/v1/jobs",
        data,
        {
            "X-Litmus-Token": app.token,
            "X-Litmus-Filename": filename,
            "Content-Type": "application/octet-stream",
        },
    )
    r = c.getresponse()
    status, value = r.status, json.loads(r.read())
    c.close()
    return status, value


@pytest.mark.parametrize(
    "name", ["bad%E2%80%AE.txt", "bad%C2%85.txt", "bad%E2%80%8B.txt"]
)
def test_display_controls_rejected(server, name):
    status, value = upload(server, name)
    assert status == 400 and value["error"]["code"] == "filename"
    assert server.service.current is None


def test_ordinary_unicode_filename_accepted(server):
    assert upload(server, "caf%C3%A9.txt")[0] == 202


def test_unexpected_error_returns_safe_json_and_recovers(server, monkeypatch, caplog):
    original = module.files
    monkeypatch.setattr(
        module,
        "files",
        lambda *args: (_ for _ in ()).throw(RuntimeError("private exception text")),
    )
    c = http.client.HTTPConnection(*server.server_address, timeout=2)
    c.request("GET", "/")
    r = c.getresponse()
    body = r.read()
    assert r.status == 500 and b"private exception" not in body
    assert json.loads(body)["error"]["code"] == "internal"
    assert "RuntimeError" in caplog.text and "private exception text" not in caplog.text
    c.close()
    monkeypatch.setattr(module, "files", original)
    assert upload(server, "normal.txt")[0] == 202


def test_trickle_upload_has_total_deadline(server, monkeypatch):
    monkeypatch.setattr(module, "UPLOAD_DEADLINE_SECONDS", 0.15)
    c = socket.create_connection(server.server_address, timeout=2)
    head = (
        f"POST /api/v1/jobs HTTP/1.1\r\nHost: {server.origin[7:]}\r\n"
        f"X-Litmus-Token: {server.token}\r\nX-Litmus-Filename: slow.txt\r\n"
        "Content-Type: application/octet-stream\r\nContent-Length: 100\r\n\r\n"
    )
    c.sendall(head.encode())
    started = time.monotonic()
    for _ in range(3):
        try:
            c.sendall(b"x")
        except OSError:
            break
        time.sleep(0.04)
    response = http.client.HTTPResponse(c)
    response.begin()
    data = response.read()
    c.close()
    assert response.status == 400 and json.loads(data)["error"]["code"] == "upload"
    assert time.monotonic() - started < 1.0
    assert server.service.current is None


def test_unexpected_post_error_is_safe(server, monkeypatch, caplog):
    def fail(*args):
        raise RuntimeError("private POST content")

    monkeypatch.setattr(server.service, "begin", fail)
    status, value = upload(server, "normal.txt")
    assert status == 500 and value["error"]["code"] == "internal"
    assert "private POST content" not in json.dumps(value) + caplog.text
    assert "RuntimeError" in caplog.text


def test_job_diagnostics_exclude_content(server, monkeypatch, caplog):
    def fail(*args):
        raise RuntimeError("private analysis content")

    monkeypatch.setattr(server.service, "analyze", fail)
    status, value = upload(server, "normal.txt")
    assert status == 202
    server.service.future.result(timeout=2)
    job = server.service.get(value["id"])
    assert job["status"] == "error"
    assert "private analysis content" not in json.dumps(job) + caplog.text
    assert "analysis (RuntimeError)" in caplog.text


@pytest.mark.parametrize("available", [False, True])
def test_index_exposes_model_stack_without_loading_it(server, monkeypatch, available):
    monkeypatch.setattr(
        module, "find_spec", lambda name: object() if available else None
    )
    c = http.client.HTTPConnection(*server.server_address, timeout=2)
    c.request("GET", "/")
    response = c.getresponse()
    assert response.status == 200
    body = response.read().decode()
    assert f'name="litmus-text-stack" content="{str(available).lower()}"' in body
    assert "@@TEXT_STACK@@" not in body
    c.close()
