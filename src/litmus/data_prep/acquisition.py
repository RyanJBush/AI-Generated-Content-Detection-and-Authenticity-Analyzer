"""Approved single-artifact acquisition with durable transfer/storage ceilings."""

import hashlib
import io
import json
import os
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

REVISION = "865cac74188466cb0c3b7574a10204007b57a459"
SIZE = 11_779_491_051
SHA256 = "52f04ceebc126064e68fbd22d8b736964065745464f4bfd52e488150b49f84e4"
TRANSFER_LIMIT = 13_000_000_000
ARTIFACT_LIMIT = 25_000_000_000
FREE_REQUIRED = 30_000_000_000
API = (
    f"https://huggingface.co/api/datasets/liamdugan/raid/revision/{REVISION}?blobs=true"
)
URL = f"https://huggingface.co/datasets/liamdugan/raid/resolve/{REVISION}/train.csv"


class PrepError(RuntimeError):
    """Stop condition; no identity/schema/budget fallback is permitted."""


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(
            value,
            stream,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def file_hash(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def directory_bytes(path: Path):
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


class Budget:
    def __init__(
        self,
        root: Path,
        *,
        transfer_limit=TRANSFER_LIMIT,
        artifact_limit=ARTIFACT_LIMIT,
        extra_roots=(),
        reserve=0,
    ):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "transfer.json"
        self.limit, self.artifact_limit = transfer_limit, artifact_limit
        self.extra_roots, self.reserve = extra_roots, reserve
        self.state = (
            json.loads(self.path.read_text(encoding="utf-8"))
            if self.path.exists()
            else {"charged_bytes": 0, "received_bytes": 0}
        )
        if self.state["charged_bytes"] > self.limit:
            raise PrepError("transfer_budget_exceeded")

    def check_storage(self, incoming=0):
        used = directory_bytes(self.root) + self.reserve
        used += sum(directory_bytes(p) for p in self.extra_roots if p.exists())
        if used + incoming > self.artifact_limit:
            raise PrepError("artifact_budget_exceeded")
        return used

    def read(self, response, maximum):
        remaining = self.limit - self.state["charged_bytes"]
        if remaining <= 0:
            raise PrepError("transfer_budget_exceeded")
        count = min(maximum, remaining)
        self.check_storage(count)
        # Reserve before read: a crash cannot make a later invocation forget
        # bytes potentially received. Unused reservations are not refunded.
        self.state["charged_bytes"] += count
        write_json(self.path, self.state)
        block = response.read(count)
        self.state["received_bytes"] += len(block)
        write_json(self.path, self.state)
        return block


def validate_metadata(value):
    if value.get("sha") != REVISION:
        raise PrepError("revision_identity_mismatch")
    matches = [
        r for r in value.get("siblings", []) if r.get("rfilename") == "train.csv"
    ]
    if len(matches) != 1:
        raise PrepError("artifact_metadata_missing_or_ambiguous")
    item = matches[0]
    lfs = item.get("lfs") or {}
    if lfs.get("size") != SIZE or lfs.get("sha256") != SHA256:
        raise PrepError("artifact_identity_mismatch")
    if "size" in item and item["size"] != SIZE:
        raise PrepError("artifact_size_mismatch")
    return {"revision": REVISION, "path": "train.csv", "bytes": SIZE, "sha256": SHA256}


def drain_response(response, budget):
    """Consume intermediate bodies only through durable, bounded reads."""
    try:
        while budget.read(response, 64 * 1024):
            pass
    finally:
        response.close()


class BudgetHTTPErrorHandler(urllib.request.HTTPDefaultErrorHandler):
    def __init__(self, budget):
        self.budget = budget

    def http_error_default(self, req, fp, code, msg, headers):
        drain_response(fp, self.budget)
        # Do not expose a live, unbudgeted body or signed URL via HTTPError.
        raise PrepError(f"http_response_error:{code}")


class ArtifactRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, budget):
        self.budget = budget
        self.hosts = []

    def http_error_302(self, req, fp, code, msg, headers):
        drain_response(fp, self.budget)
        if "location" not in headers and "uri" not in headers:
            raise PrepError("redirect_location_missing")
        # urllib's redirect implementation calls fp.read() without a bound.
        # It may now consume only this empty surrogate; the real body is closed.
        with io.BytesIO() as empty:
            return super().http_error_302(req, empty, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not (
            host == "huggingface.co"
            or host.endswith(".huggingface.co")
            or host.endswith(".hf.co")
        ):
            raise PrepError("unapproved_redirect_host")
        self.hosts.append(host)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def acquire(repo: Path, *, preflight_only=False):
    if shutil.disk_usage(repo).free < FREE_REQUIRED:
        raise PrepError("insufficient_free_space")
    root = repo / "data/raid"
    manifest_dir = repo / "eval/manifests/r1e"
    budget = Budget(root, extra_roots=(manifest_dir,), reserve=64 * 1024 * 1024)
    redirects = ArtifactRedirect(budget)
    opener = urllib.request.build_opener(redirects, BudgetHTTPErrorHandler(budget))
    start = time.monotonic()
    request = urllib.request.Request(API, headers={"Cache-Control": "no-cache"})
    with opener.open(request, timeout=60) as response:
        content = budget.read(response, 1024 * 1024)
    identity = validate_metadata(json.loads(content))
    free_before = shutil.disk_usage(repo).free
    receipt = {
        "identity": identity,
        "preflight": "PASS",
        "metadata_url": API,
        "payload_url": URL,
        "free_bytes_before": free_before,
        "license_declared": "MIT",
        "use": "local evaluation only",
        "license_source": "https://huggingface.co/datasets/liamdugan/raid",
        "approval_date": "2026-10-31",
    }
    write_json(manifest_dir / "preflight.json", receipt)
    print("Pinned revision/size/SHA-256 API preflight PASS", flush=True)
    if preflight_only:
        return receipt
    destination = root / REVISION / "train.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".csv.part")
    if not destination.exists():
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > SIZE:
            raise PrepError("partial_file_size_invalid")
        if offset < SIZE:
            headers = {"Cache-Control": "no-cache"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            # Fresh signed redirect for this immutable object; no mutable ref.
            request = urllib.request.Request(
                URL + f"?download=true&litmus_request={time.time_ns()}", headers=headers
            )
            with opener.open(request, timeout=60) as response:
                if offset:
                    expected = f"bytes {offset}-{SIZE - 1}/{SIZE}"
                    if (
                        response.status != 206
                        or response.headers.get("Content-Range") != expected
                    ):
                        raise PrepError("resume_range_not_verified")
                elif response.status != 200:
                    raise PrepError("unexpected_download_status")
                if int(response.headers.get("Content-Length", -1)) != SIZE - offset:
                    raise PrepError("download_length_header_mismatch")
                with partial.open("ab" if offset else "xb") as stream:
                    last = time.monotonic()
                    while offset < SIZE:
                        maximum = min(8 * 1024 * 1024, SIZE - offset)
                        block = budget.read(response, maximum)
                        if not block:
                            raise PrepError("incomplete_download")
                        stream.write(block)
                        offset += len(block)
                        if time.monotonic() - last > 10:
                            print(f"Downloaded {offset:,}/{SIZE:,} bytes", flush=True)
                            last = time.monotonic()
                    stream.flush()
                    os.fsync(stream.fileno())
        if partial.stat().st_size != SIZE or file_hash(partial) != SHA256:
            raise PrepError("downloaded_length_or_hash_mismatch")
        partial.rename(destination)
    if destination.stat().st_size != SIZE or file_hash(destination) != SHA256:
        raise PrepError("existing_artifact_identity_mismatch")
    receipt.update(
        {
            "download_verification": "PASS",
            "local_path": str(destination),
            "computed_sha256": SHA256,
            "local_bytes": SIZE,
            "elapsed_seconds": time.monotonic() - start,
            "transfer": budget.state,
            "redirect_hosts": redirects.hosts,
            "artifact_bytes_with_reserve": budget.check_storage(),
        }
    )
    write_json(manifest_dir / "acquisition.json", receipt)
    print("Downloaded length and SHA-256 PASS", flush=True)
    return receipt
