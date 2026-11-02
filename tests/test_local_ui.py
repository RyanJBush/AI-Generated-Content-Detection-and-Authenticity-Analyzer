"""Real loopback contract tests using constructed uploads and no model weights."""

import http.client
import json
import threading
import time
from pathlib import Path

import pytest

from litmus.local_ui.server import make_server
from litmus.report import run_analysis


@pytest.fixture
def ui():
    servers = []

    def create(analyze=None):
        server = make_server(0, analyze=analyze)
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        servers.append((server, thread))
        return server

    yield create
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        server.service.close()
        thread.join(3)


def request(server, method, path, data=None, headers=None):
    connection = http.client.HTTPConnection(*server.server_address, timeout=4)
    default = {"X-Litmus-Token": server.token}
    if data is not None:
        default.update(
            {
                "X-Litmus-Filename": "sample.txt",
                "Content-Type": "application/octet-stream",
            }
        )
    default.update(headers or {})
    connection.request(method, path, data, default)
    response = connection.getresponse()
    body = response.read()
    result = response.status, dict(response.getheaders()), body
    connection.close()
    return result


def wait_job(server, rid):
    for _ in range(200):
        status, _, body = request(server, "GET", "/api/v1/jobs/" + rid)
        assert status == 200
        job = json.loads(body)
        if job["status"] != "running":
            return job
        time.sleep(0.01)
    raise AssertionError("constructed job did not finish")


def assert_contract(job):
    spec = json.loads(
        (
            Path(__file__).resolve().parents[1] / "docs/api/local-ui.openapi.json"
        ).read_text(encoding="utf-8")
    )
    schema = spec["components"]["schemas"]["Job"]
    assert set(job) == set(schema["required"])
    assert job["status"] in schema["properties"]["status"]["enum"]
    assert len(job["id"]) == 32
    if job["status"] == "completed":
        assert job["report"]["report_schema"] == "litmus-report/r0"
        assert job["error"] is None
    elif job["status"] == "error":
        assert job["report"] is None and isinstance(job["error"], str)


def test_upload_poll_report_contract_defaults_and_cleanup(ui):
    paths, options_seen = [], []

    def analyze(path, options):
        paths.append(Path(path))
        options_seen.append(options)
        return run_analysis(path)

    server = ui(analyze)
    status, headers, body = request(server, "POST", "/api/v1/jobs", b"A sample text.")
    assert status == 202
    first = json.loads(body)
    assert_contract(first)
    assert headers["Location"] == "/api/v1/jobs/" + first["id"]
    job = wait_job(server, first["id"])
    assert_contract(job)
    assert job["report"]["input"]["file_name"] == "sample.txt"
    assert options_seen == [{"text_origin": False, "quality": False, "c2pa": False}]
    assert not paths[0].exists() and paths[0].name != "sample.txt"
    assert (
        job["report"]["segments"][0]["origin"][0]["method_id"]
        == "text_origin_placeholder"
    )
    assert request(server, "GET", "/api/v1/jobs/" + "0" * 32)[0] == 404
    assert json.loads(request(server, "GET", "/api/v1/jobs/" + first["id"])[2]) == job


def test_busy_bounded_worker_error_cleanup_and_recovery(ui):
    release = threading.Event()
    paths, threads = [], []

    def analyze(path, options):
        paths.append(Path(path))
        threads.append(threading.get_ident())
        release.wait(3)
        if len(paths) == 1:
            raise RuntimeError("constructed analysis failure")
        return run_analysis(path)

    server = ui(analyze)
    try:
        _, _, body = request(server, "POST", "/api/v1/jobs", b"first")
        first = json.loads(body)
        assert (
            json.loads(request(server, "GET", "/api/v1/jobs/" + first["id"])[2])[
                "status"
            ]
            == "running"
        )
        assert request(server, "POST", "/api/v1/jobs", b"second")[0] == 409
    finally:
        release.set()
    failed = wait_job(server, first["id"])
    assert_contract(failed)
    assert failed["status"] == "error" and not paths[0].exists()
    _, _, body = request(server, "POST", "/api/v1/jobs", b"recovery")
    second = json.loads(body)
    assert wait_job(server, second["id"])["status"] == "completed"
    assert len(set(threads)) == 1 and len(paths) == 2
    assert request(server, "GET", "/api/v1/jobs/" + first["id"])[0] == 404


@pytest.mark.parametrize(
    "path,headers,expected",
    [
        ("/api/v1/jobs", {"X-Litmus-Token": "wrong"}, 403),
        ("/api/v1/jobs", {"X-Litmus-Token": "\u00e9"}, 403),
        ("/api/v1/jobs", {"Host": "external.test"}, 403),
        ("/api/v1/jobs", {"Origin": "https://external.test"}, 403),
        ("/api/v1/jobs?quality=yes", {}, 400),
        ("/api/v1/jobs?quality=on&quality=off", {}, 400),
        ("/api/v1/jobs?path=file", {}, 400),
        ("/api/v1/jobs", {"X-Litmus-Filename": "../file.txt"}, 400),
        ("/api/v1/jobs", {"X-Litmus-Filename": "a%5Cfile.txt"}, 400),
        ("/api/v1/jobs", {"X-Litmus-Filename": "%ZZ.txt"}, 400),
        ("/api/v1/jobs", {"X-Litmus-Filename": "%FF.txt"}, 400),
        ("/api/v1/jobs", {"Content-Type": "text/plain"}, 415),
        ("/api/v1/jobs", {"Content-Length": "-1"}, 400),
        ("/api/v1/jobs", {"Content-Length": "50000001"}, 413),
        ("/api/v1/jobs", {"Transfer-Encoding": "chunked"}, 400),
        ("/missing", {}, 404),
    ],
)
def test_rejected_requests_create_no_job(ui, path, headers, expected):
    calls = []
    server = ui(lambda *args: calls.append(args))
    status, _, body = request(server, "POST", path, b"input", headers)
    assert status == expected and not calls
    assert set(json.loads(body)) == {"error"}


def test_repeated_framing_rejections_deliver_json(ui):
    calls = []
    server = ui(lambda *args: calls.append(args))
    for _ in range(100):
        status, _, body = request(
            server, "POST", "/api/v1/jobs", b"input",
            {"Transfer-Encoding": "chunked"},
        )
        assert status == 400 and set(json.loads(body)) == {"error"}
    assert not calls


@pytest.mark.parametrize(
    "name",
    [
        "Host",
        "Origin",
        "X-Litmus-Token",
        "Content-Length",
        "X-Litmus-Filename",
        "Content-Type",
    ],
)
def test_duplicate_security_or_framing_headers_rejected(ui, name):
    server = ui()
    c = http.client.HTTPConnection(*server.server_address, timeout=3)
    c.putrequest("POST", "/api/v1/jobs", skip_host=True)
    headers = {
        "Host": f"127.0.0.1:{server.server_port}",
        "X-Litmus-Token": server.token,
        "Origin": server.origin,
        "Content-Length": "1",
        "Content-Type": "application/octet-stream",
        "X-Litmus-Filename": "sample.txt",
    }
    for key, value in headers.items():
        c.putheader(key, value)
        if key == name:
            c.putheader(key, value)
    c.endheaders(b"x")
    response = c.getresponse()
    assert response.status in (400, 403)
    response.read()
    c.close()


def test_static_security_no_path_read_and_rejected_ingestion(ui):
    server = ui()
    status, headers, body = request(server, "GET", "/")
    assert status == 200 and server.token.encode() in body
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-store"
    assert request(server, "GET", "/../../README.md")[0] == 404
    assert request(server, "GET", "/app.js")[0] == 200
    assert request(server, "GET", "/style.css")[0] == 200
    _, _, body = request(server, "POST", "/api/v1/jobs", b"")
    job = wait_job(server, json.loads(body)["id"])
    assert job["status"] == "completed" and job["report"]["segments"] == []


def test_short_upload_preserves_previous_report(ui):
    import socket

    server = ui()
    _, _, body = request(server, "POST", "/api/v1/jobs", b"previous text")
    rid = json.loads(body)["id"]
    previous = wait_job(server, rid)
    c = http.client.HTTPConnection(*server.server_address, timeout=3)
    c.putrequest("POST", "/api/v1/jobs")
    for name, value in {
        "X-Litmus-Token": server.token,
        "X-Litmus-Filename": "short.txt",
        "Content-Type": "application/octet-stream",
        "Content-Length": "8",
    }.items():
        c.putheader(name, value)
    c.endheaders(b"x")
    c.sock.shutdown(socket.SHUT_WR)
    response = c.getresponse()
    assert response.status == 400
    response.read()
    c.close()
    assert json.loads(request(server, "GET", "/api/v1/jobs/" + rid)[2]) == previous


def test_adapter_reuses_one_analyzer_and_close_releases_it(monkeypatch):
    from litmus.local_ui.analysis import Analyzers
    from litmus.schemas import OriginEvidence, OriginResult
    from litmus.scorer import analyzer

    made = []

    class FakeAnalyzer:
        def __init__(self, *, device):
            assert device == "cuda"
            made.append(self)

        def __call__(self, text):
            return OriginEvidence("constructed", "test", OriginResult.INCONCLUSIVE)

    monkeypatch.setattr(analyzer, "BinocularsAnalyzer", FakeAnalyzer)
    seen = []
    import litmus.report

    def fake_report(path, origin, quality, *, c2pa_enabled):
        seen.append(origin)
        return {"constructed": True}

    monkeypatch.setattr(litmus.report, "run_analysis", fake_report)
    adapter = Analyzers()
    on = {"text_origin": True, "quality": False, "c2pa": False}
    adapter("constructed", on)
    adapter("constructed", on)
    adapter("constructed", {**on, "text_origin": False})
    assert len(made) == 1 and seen == [made[0], made[0], None]
    adapter.close()
    assert adapter.origin is adapter.observers is None


def test_ui_import_isolated_from_models_and_evaluation():
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import litmus.local_ui.server; "
            "assert not any(n.startswith(('torch','transformers',"
            "'litmus.evaluation','litmus.data_prep')) for n in sys.modules)",
        ],
        check=True,
    )


def test_arbitrary_unsupported_method_returns_json_error(ui):
    server = ui()
    status, headers, body = request(server, "PROPFIND", "/api/v1/jobs")
    assert status == 501 and headers["Content-Type"].startswith("application/json")
    assert set(json.loads(body)) == {"error"}


@pytest.mark.parametrize("method", ["OPTIONS", "DELETE", "HEAD"])
def test_named_unsupported_methods_also_check_host(ui, method):
    status, _, _ = request(
        ui(), method, "/api/v1/jobs", headers={"Host": "external.test"}
    )
    assert status == 403
