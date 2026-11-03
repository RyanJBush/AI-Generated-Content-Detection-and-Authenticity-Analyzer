"""Single-user loopback interface, bounded uploads and one analysis worker."""

import argparse
import copy
import hmac
import json
import logging
import re
import secrets
import socket
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, unquote_to_bytes, urlsplit
from uuid import uuid4

MAX_UPLOAD = 50_000_000
UPLOAD_DEADLINE_SECONDS = 10.0
LOGGER = logging.getLogger(__name__)
OPTIONS = ("text_origin", "quality", "c2pa")
SECURITY_HEADERS = (
    "Host",
    "Origin",
    "X-Litmus-Token",
    "X-Litmus-Filename",
    "Content-Length",
    "Content-Type",
)
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)


class BusyError(Exception):
    pass


class Jobs:
    def __init__(self, analyze):
        self.analyze = analyze
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="litmus-analysis"
        )
        self.current = self.future = None

    def busy(self):
        with self.lock:
            return self.future is not None and not self.future.done()

    def begin(self, data, name, options):
        with self.lock:
            if self.future is not None and not self.future.done():
                raise BusyError
            self.current = {
                "id": uuid4().hex,
                "status": "running",
                "report": None,
                "error": None,
            }
            self.future = self.pool.submit(self._run, data, name, options)
            return copy.deepcopy(self.current)

    def _run(self, data, name, options):
        phase = "analysis"
        try:
            with TemporaryDirectory(prefix="litmus-upload-") as directory:
                suffix = Path(name).suffix
                if not re.fullmatch(r"\.[A-Za-z0-9]{1,16}", suffix):
                    suffix = ".upload"
                path = Path(directory) / (uuid4().hex + suffix)
                path.write_bytes(data)
                report = self.analyze(str(path), options)
                report["input"]["file_name"] = name
                json.dumps(report, ensure_ascii=False, allow_nan=False)
                phase = "temporary cleanup"
            # Directory cleanup occurs before exposing completion.
            with self.lock:
                self.current.update(status="completed", report=report)
        except Exception as error:
            LOGGER.error(
                "Litmus job failed during %s (%s)", phase, type(error).__name__
            )
            # Never echo raw input or a traceback to the browser.
            message = "Analysis could not finish. Check the file and local model setup."
            if type(error).__name__ == "C2paUnavailable":
                message = str(error)
            with self.lock:
                self.current.update(status="error", error=message)

    def get(self, rid):
        with self.lock:
            if self.current is None or rid != self.current["id"]:
                return None
            return copy.deepcopy(self.current)

    def close(self):
        # A disconnect/timeout is not cancellation of native analysis work.
        self.pool.shutdown(wait=True, cancel_futures=False)
        close = getattr(self.analyze, "close", None)
        if close:
            close()


class LocalServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, port, analyze):
        super().__init__(("127.0.0.1", port), Handler)
        self.token = secrets.token_urlsafe(32)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.service = Jobs(analyze)


class Handler(BaseHTTPRequestHandler):
    server_version = "Litmus"
    sys_version = ""
    timeout = 10

    def handle_one_request(self):
        self._response_started = False
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        except Exception as error:
            LOGGER.error("Litmus request failed (%s)", type(error).__name__)
            self.close_connection = True
            if not self._response_started:
                self._error(500, "internal", "The local request failed. Try again.")

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler dispatches unlisted methods here.
        if code == 501 and self._guard() is None:
            return
        self._error(code, "http", message or "The local request was rejected.")

    def _send(self, status, body, mime="application/json; charset=utf-8", **extra):
        self._response_started = True
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in extra.items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status, value, **headers):
        self._send(
            status,
            json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            **headers,
        )

    def _error(self, status, code, message):
        self._json(status, {"error": {"code": code, "message": message}})
        # Winsock may reset a closed socket with an unread body before the
        # client receives its error. Rejected framing may have no usable length.
        # Drain raw bytes without interpreting it, with both byte/time bounds.
        try:
            self.wfile.flush()
            deadline = time.monotonic() + 0.05
            remaining = 65536
            while remaining and (wait := deadline - time.monotonic()) > 0:
                self.connection.settimeout(wait)
                chunk = self.rfile.read1(remaining)
                if not chunk:
                    break
                remaining -= len(chunk)
        except (OSError, ValueError):
            pass
        try:
            self.connection.shutdown(socket.SHUT_WR)
        except (OSError, ValueError):
            pass

    def _guard(self):
        for key in SECURITY_HEADERS:
            if len(self.headers.get_all(key, [])) > 1:
                self._error(400, "duplicate_header", "Duplicate request header.")
                return None
        if self.headers.get("Host") != self.server.origin.removeprefix("http://"):
            self._error(403, "host", "Use the printed 127.0.0.1 address.")
            return None
        if self.headers.get("Origin", self.server.origin) != self.server.origin:
            self._error(403, "origin", "Open Litmus from its local address.")
            return None
        if self.headers.get_all("Transfer-Encoding"):
            self._error(400, "framing", "Transfer encoding is not supported.")
            return None
        try:
            target = urlsplit(self.path)
        except ValueError:
            self._error(400, "target", "Use a valid local resource path.")
            return None
        if target.scheme or target.netloc or target.fragment:
            self._error(400, "target", "Use a local resource path.")
            return None
        if target.path.startswith("/api/") and not hmac.compare_digest(
            self.headers.get("X-Litmus-Token", "").encode("utf-8"),
            self.server.token.encode("ascii"),
        ):
            self._error(403, "token", "Reload this Litmus page and try again.")
            return None
        return target

    def do_GET(self):
        target = self._guard()
        if target is None:
            return
        if target.query or self.headers.get("Content-Length", "0") != "0":
            self._error(400, "parameters", "Unexpected query or request body.")
            return
        assets = {
            "/": ("index.html", "text/html"),
            "/app.js": ("app.js", "text/javascript"),
            "/style.css": ("style.css", "text/css"),
        }
        if target.path in assets:
            name, mime = assets[target.path]
            body = files("litmus.local_ui").joinpath("static", name).read_bytes()
            if name == "index.html":
                body = body.replace(b"@@TOKEN@@", self.server.token.encode("ascii"))
                available = all(
                    find_spec(module) is not None
                    for module in ("torch", "transformers")
                )
                body = body.replace(
                    b"@@TEXT_STACK@@", b"true" if available else b"false"
                )
            self._send(200, body, mime + "; charset=utf-8")
        elif re.fullmatch(r"/api/v1/jobs/[0-9a-f]{32}", target.path):
            job = self.server.service.get(target.path.rsplit("/", 1)[1])
            if job is None:
                self._error(
                    404,
                    "job",
                    "This report is no longer available. Analyze the file again.",
                )
            else:
                self._json(200, job)
        else:
            self._error(404, "resource", "Local resource not found.")

    def do_POST(self):
        target = self._guard()
        if target is None:
            return
        if target.path != "/api/v1/jobs":
            self._error(404, "resource", "Local resource not found.")
            return
        query = parse_qs(target.query, keep_blank_values=True)
        if set(query) - set(OPTIONS) or any(
            len(v) != 1 or v[0] not in ("off", "on") for v in query.values()
        ):
            self._error(
                400, "options", "Choose on or off once for each analysis option."
            )
            return
        length = self.headers.get("Content-Length")
        if length is None:
            self._error(411, "length", "A file length is required.")
            return
        if not re.fullmatch(r"[0-9]{1,12}", length):
            self._error(400, "length", "Invalid file length.")
            return
        length = int(length)
        if length > MAX_UPLOAD:
            self._error(413, "size", "Choose a file no larger than 50 MB.")
            return
        if self.headers.get("Content-Type") != "application/octet-stream":
            self._error(415, "media", "Upload the file as binary data.")
            return
        encoded = self.headers.get("X-Litmus-Filename", "")
        try:
            if (
                len(encoded) > 3000
                or re.search(r"%(?![0-9a-fA-F]{2})", encoded)
                or not encoded.isascii()
            ):
                raise ValueError
            name = unquote_to_bytes(encoded).decode("utf-8", errors="strict")
            if (
                not name
                or name in (".", "..")
                or len(name) > 180
                or len(name.encode("utf-8")) > 255
                or any(
                    unicodedata.category(c) in {"Cc", "Cf"} or c in "/\\"
                    for c in name
                )
            ):
                raise ValueError
        except (ValueError, UnicodeError):
            self._error(400, "filename", "Choose a file with a valid basename.")
            return
        if self.server.service.busy():
            self._error(
                409, "busy", "An analysis is already running. Wait for it to finish."
            )
            return
        try:
            deadline = time.monotonic() + UPLOAD_DEADLINE_SECONDS
            data = bytearray()
            while len(data) < length:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("upload deadline")
                self.connection.settimeout(remaining)
                chunk = self.rfile.read1(min(65536, length - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            data = bytes(data)
        except (socket.timeout, OSError):
            self._error(
                400, "upload", "Upload did not finish within 10 seconds. "
                "Try a smaller file or copy it to a local folder first."
            )
            return
        if len(data) != length:
            self._error(400, "upload", "Upload did not finish. Try again.")
            return
        try:
            job = self.server.service.begin(
                data, name, {k: query.get(k, ["off"])[0] == "on" for k in OPTIONS}
            )
        except BusyError:
            self._error(
                409, "busy", "An analysis is already running. Wait for it to finish."
            )
            return
        self._json(202, job, Location="/api/v1/jobs/" + job["id"])

    def do_OPTIONS(self):
        self.send_error(501, "This HTTP method is not supported.")

    do_PUT = do_DELETE = do_PATCH = do_HEAD = do_TRACE = do_CONNECT = do_OPTIONS


def make_server(port=8765, *, analyze=None):
    if analyze is None:
        from litmus.local_ui.analysis import Analyzers

        analyze = Analyzers()
    return LocalServer(port, analyze)


def main():
    parser = argparse.ArgumentParser(
        description="Open Litmus's local file-to-report interface."
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        server = make_server(args.port)
    except OSError as error:
        parser.exit(1, f"Cannot start Litmus: {error}. Try another --port.\n")
    print(
        f"Litmus is ready: {server.origin}\n"
        "Open that address in your browser. Ctrl+C stops the server.\n"
        "Analysis continues after a tab closes; shutdown waits for active work.",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print("\nStopping Litmus; waiting for active analysis...", flush=True)
    finally:
        server.server_close()
        server.service.close()
