import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from litmus.offline import (
    NetworkAccessBlocked,
    SubprocessBlocked,
    offline_guards,
    socket_guard,
    subprocess_guard,
)

# TEST-NET-1 / documentation ranges (RFC 5737, RFC 3849): never routed
NON_LOOPBACK_V4 = "192.0.2.1"
NON_LOOPBACK_V6 = "2001:db8::1"


# --- loopback trap: positive control (B4) ---

def test_trap_positive_control_records_connection(trap):
    with socket_guard():
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(trap.url + "/control", timeout=5)
    assert exc.value.code == 404
    assert len(trap.connections) == 1
    assert trap.requests == ["/control"]


def test_trap_records_raw_tcp_connection(trap):
    with socket.create_connection((trap.host, trap.port), timeout=5):
        pass
    # Accept happens on the server thread; wait up to 5 s for the record
    deadline = time.monotonic() + 5
    while not trap.connections and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(trap.connections) == 1


# --- socket guard ---

def test_socket_guard_allows_ipv4_loopback(trap):
    with socket_guard():
        with socket.create_connection(("127.0.0.1", trap.port), timeout=5):
            pass


def test_socket_guard_allows_ipv6_loopback():
    if not socket.has_ipv6:
        pytest.fail("IPv6 unavailable; cannot test ::1 (not expected on this host)")
    server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    server.bind(("::1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        with socket_guard():
            client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            client.settimeout(5)
            client.connect(("::1", port))
            client.close()
    finally:
        server.close()


@pytest.mark.parametrize(
    "family, host",
    [(socket.AF_INET, NON_LOOPBACK_V4), (socket.AF_INET6, NON_LOOPBACK_V6)],
)
def test_socket_guard_blocks_non_loopback_connect(family, host):
    with socket_guard():
        s = socket.socket(family, socket.SOCK_STREAM)
        try:
            with pytest.raises(NetworkAccessBlocked, match="loopback only"):
                s.connect((host, 80))
            with pytest.raises(NetworkAccessBlocked):
                s.connect_ex((host, 80))
        finally:
            s.close()


def test_socket_guard_blocks_udp_sendto():
    with socket_guard():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            with pytest.raises(NetworkAccessBlocked):
                s.sendto(b"x", (NON_LOOPBACK_V4, 53))
        finally:
            s.close()


def test_socket_guard_blocks_name_lookup_and_urlopen():
    with socket_guard():
        with pytest.raises(NetworkAccessBlocked, match="name lookup"):
            socket.getaddrinfo("example.com", 80)
        with pytest.raises(NetworkAccessBlocked):
            socket.gethostbyname("example.com")
        with pytest.raises((NetworkAccessBlocked, urllib.error.URLError)) as exc:
            urllib.request.urlopen("http://example.com/", timeout=5)
        # urllib may wrap the guard error; the cause must still be the guard
        err = exc.value
        if isinstance(err, urllib.error.URLError):
            assert isinstance(err.reason, NetworkAccessBlocked)


def test_socket_guard_restores_on_exit():
    before = (socket.socket.connect, socket.getaddrinfo)
    with socket_guard():
        assert socket.socket.connect is not before[0]
    assert (socket.socket.connect, socket.getaddrinfo) == before


# --- subprocess guard ---

def test_subprocess_guard_blocks_launchers():
    with subprocess_guard():
        with pytest.raises(SubprocessBlocked):
            subprocess.run([sys.executable, "-c", "pass"])
        with pytest.raises(SubprocessBlocked):
            subprocess.Popen([sys.executable, "-c", "pass"])
        with pytest.raises(SubprocessBlocked):
            os.system("echo blocked")
        with pytest.raises(SubprocessBlocked):
            os.popen("echo blocked")


def test_subprocess_guard_restores_on_exit():
    with subprocess_guard():
        pass
    result = subprocess.run([sys.executable, "-c", "print('ok')"],
                            capture_output=True, text=True)
    assert result.stdout.strip() == "ok"


def test_ingestion_runs_under_offline_guards(tmp_path):
    text = tmp_path / "a.txt"
    text.write_bytes(b"Hello offline world")
    png = tmp_path / "a.png"
    from PIL import Image
    Image.new("RGB", (2, 2)).save(png, format="PNG")

    from litmus.ingestion import analyze_ingestion
    with offline_guards():
        assert analyze_ingestion(str(text)) == {"result": "supported",
                                                "mime": "text/plain"}
        assert analyze_ingestion(str(png)) == {"result": "supported",
                                               "mime": "image/png"}


def test_offline_guards_set_env_and_restore(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    with offline_guards():
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
        with pytest.raises(SubprocessBlocked):
            subprocess.run([sys.executable, "-c", "pass"])
        with pytest.raises(NetworkAccessBlocked):
            socket.create_connection((NON_LOOPBACK_V4, 80), timeout=1)
    assert "HF_HUB_OFFLINE" not in os.environ
    assert "TRANSFORMERS_OFFLINE" not in os.environ
