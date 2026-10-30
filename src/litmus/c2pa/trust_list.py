"""Packaged production trust-anchor list (R1-D plan §h, §p Correction 4).

Litmus's policy in R1: the production trust list is explicit, packaged,
versioned and EMPTY. It is loaded only through importlib.resources. What the
SDK itself does about trust (built-in anchors or not) is an observation
recorded elsewhere, never assumed here.

File format (UTF-8, LF only): six ``# key: value`` header lines in a fixed
order (name, version, date, license, policy, format), then zero or more PEM
certificate blocks. Blank lines are ignored; any other content is an error.
"""
import datetime
import hashlib
import importlib.resources
import re
from dataclasses import dataclass
from typing import Tuple

PRODUCTION_NAME = "production_trust_anchors"
HEADER_KEYS = ("name", "version", "date", "license", "policy", "format")
_PEM = re.compile(r"-----BEGIN CERTIFICATE-----\n[A-Za-z0-9+/=\n]+"
                  r"-----END CERTIFICATE-----\n")


class TrustListError(ValueError):
    pass


@dataclass(frozen=True)
class TrustList:
    name: str
    version: int
    date: str
    license: str
    anchors: Tuple[str, ...]
    sha256: str


def parse_trust_list(data: bytes, expected_name: str) -> TrustList:
    if b"\r" in data:
        raise TrustListError("carriage return found (LF line endings only)")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise TrustListError(f"not UTF-8: {e}") from None
    lines = text.split("\n")
    header = {}
    for i, key in enumerate(HEADER_KEYS):
        prefix = f"# {key}: "
        if i >= len(lines) or not lines[i].startswith(prefix) \
                or not lines[i][len(prefix):].strip():
            raise TrustListError(f"header line {i + 1} must be '# {key}: <value>'")
        header[key] = lines[i][len(prefix):].strip()
    if header["name"] != expected_name:
        raise TrustListError(f"header name {header['name']!r} is not "
                             f"{expected_name!r}")
    if not header["version"].isdigit() or int(header["version"]) < 1:
        raise TrustListError("version must be a positive integer")
    try:
        datetime.date.fromisoformat(header["date"])
    except ValueError:
        raise TrustListError("date must be ISO 8601 (YYYY-MM-DD)") from None
    body = "\n".join(lines[len(HEADER_KEYS):])
    anchors = tuple(_PEM.findall(body))
    if _PEM.sub("", body).strip():
        raise TrustListError("content other than PEM certificate blocks")
    return TrustList(name=header["name"], version=int(header["version"]),
                     date=header["date"], license=header["license"],
                     anchors=anchors, sha256=hashlib.sha256(data).hexdigest())


def resource_bytes(name: str) -> bytes:
    """Raw bytes of a packaged trust list, via importlib.resources only."""
    return (importlib.resources.files("litmus.c2pa")
            .joinpath("trust", f"{name}.pem").read_bytes())


def load_production_trust_list() -> TrustList:
    return parse_trust_list(resource_bytes(PRODUCTION_NAME), PRODUCTION_NAME)
