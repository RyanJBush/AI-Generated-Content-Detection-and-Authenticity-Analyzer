import http.server
import threading

import pytest

from litmus.offline import socket_guard


@pytest.fixture(autouse=True)
def _loopback_only():
    # SPEC §7: the model-free suite runs with the socket guard active
    with socket_guard():
        yield


class _TrapServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _TrapHandler)
        self.connections = []  # (client_address,) per accepted connection
        self.requests = []  # request paths seen
        self._lock = threading.Lock()

    def process_request(self, request, client_address):
        # Record at accept time, before any bytes are read
        with self._lock:
            self.connections.append(client_address)
        super().process_request(request, client_address)


class _TrapHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        with self.server._lock:
            self.server.requests.append(self.path)
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class Trap:
    def __init__(self, server):
        self._server = server
        self.host, self.port = server.server_address[:2]
        self.url = f"http://{self.host}:{self.port}"

    @property
    def connections(self):
        with self._server._lock:
            return list(self._server.connections)

    @property
    def requests(self):
        with self._server._lock:
            return list(self._server.requests)


@pytest.fixture
def trap():
    """Loopback HTTP listener on 127.0.0.1:<random port> recording connections."""
    server = _TrapServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Trap(server)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
