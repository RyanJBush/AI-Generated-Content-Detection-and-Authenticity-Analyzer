"""Process-level offline guards (SPEC §7, Addendum A1.3).

These are defense in depth, not the offline guarantee: they only see
connections made through Python's ``socket`` module and processes started
through ``subprocess`` / ``os``. Native libraries (e.g. the c2pa-rs core)
bypass them and must be disabled through their own settings (A1.2).
"""
import contextlib
import ipaddress
import os
import socket
import subprocess
from typing import Any, Iterator

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
# Names resolved locally without a network query
_LOCAL_NAMES = frozenset({"localhost"})

OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}


class NetworkAccessBlocked(RuntimeError):
    """Raised when code attempts a non-loopback network operation."""


class SubprocessBlocked(RuntimeError):
    """Raised when code attempts to start a process while analysis runs."""


def _host_of(address: Any) -> Any:
    if isinstance(address, tuple) and address:
        return address[0]
    return address


def _check_destination(sock: socket.socket, address: Any) -> None:
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        raise NetworkAccessBlocked(
            f"socket family {sock.family!r} blocked by offline guard"
        )
    host = _host_of(address)
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host not in LOOPBACK_HOSTS:
        raise NetworkAccessBlocked(
            f"connection to {host!r} blocked by offline guard (loopback only)"
        )


def _check_lookup(host: Any) -> None:
    if host is None:
        return
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host in _LOCAL_NAMES:
        return
    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise NetworkAccessBlocked(
            f"name lookup for {host!r} blocked by offline guard"
        ) from None


@contextlib.contextmanager
def socket_guard() -> Iterator[None]:
    """Allow socket connections to 127.0.0.1 and ::1 only; raise otherwise.

    Name lookups are allowed only for IP literals and ``localhost``, so no
    DNS query can leave the machine through Python's resolver functions.
    """
    cls = socket.socket
    saved = {
        "connect": cls.connect,
        "connect_ex": cls.connect_ex,
        "sendto": cls.sendto,
        "getaddrinfo": socket.getaddrinfo,
        "gethostbyname": socket.gethostbyname,
        "gethostbyname_ex": socket.gethostbyname_ex,
    }

    def connect(self, address):
        _check_destination(self, address)
        return saved["connect"](self, address)

    def connect_ex(self, address):
        _check_destination(self, address)
        return saved["connect_ex"](self, address)

    def sendto(self, data, *args):
        _check_destination(self, args[-1])
        return saved["sendto"](self, data, *args)

    def getaddrinfo(host, *args, **kwargs):
        _check_lookup(host)
        return saved["getaddrinfo"](host, *args, **kwargs)

    def gethostbyname(host):
        _check_lookup(host)
        return saved["gethostbyname"](host)

    def gethostbyname_ex(host):
        _check_lookup(host)
        return saved["gethostbyname_ex"](host)

    cls.connect = connect
    cls.connect_ex = connect_ex
    cls.sendto = sendto
    socket.getaddrinfo = getaddrinfo
    socket.gethostbyname = gethostbyname
    socket.gethostbyname_ex = gethostbyname_ex
    try:
        yield
    finally:
        cls.connect = saved["connect"]
        cls.connect_ex = saved["connect_ex"]
        cls.sendto = saved["sendto"]
        socket.getaddrinfo = saved["getaddrinfo"]
        socket.gethostbyname = saved["gethostbyname"]
        socket.gethostbyname_ex = saved["gethostbyname_ex"]


# os-level process launchers patched alongside subprocess.Popen
_OS_LAUNCHERS = (
    "system", "popen", "startfile", "posix_spawn", "posix_spawnp",
    "spawnl", "spawnle", "spawnlp", "spawnlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "execl", "execle", "execlp", "execlpe",
    "execv", "execve", "execvp", "execvpe",
)


@contextlib.contextmanager
def subprocess_guard() -> Iterator[None]:
    """Make every process launch through subprocess or os raise."""
    saved_execute = subprocess.Popen._execute_child
    saved_os = {name: getattr(os, name) for name in _OS_LAUNCHERS if hasattr(os, name)}

    def blocked(name):
        def _raise(*args, **kwargs):
            raise SubprocessBlocked(f"{name} blocked during analysis")
        return _raise

    subprocess.Popen._execute_child = blocked("subprocess.Popen")
    for name in saved_os:
        setattr(os, name, blocked(f"os.{name}"))
    try:
        yield
    finally:
        subprocess.Popen._execute_child = saved_execute
        for name, func in saved_os.items():
            setattr(os, name, func)


@contextlib.contextmanager
def offline_guards() -> Iterator[None]:
    """Everything analysis runs under: offline env, socket and subprocess guards."""
    saved_env = {k: os.environ.get(k) for k in OFFLINE_ENV}
    os.environ.update(OFFLINE_ENV)
    try:
        with socket_guard(), subprocess_guard():
            yield
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
