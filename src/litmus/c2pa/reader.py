"""One C2PA read and the narrow remote-reference adapter (R1-D2; plan §e).

``read_store`` runs on the C2PA worker: it builds the settings from a config
dict (``settings.build_settings``), reads the bytes from memory and returns a
``ReadOutcome``. Every library object it creates is closed before it returns.

Error classification (``classify_error``):

- ``C2paError.ManifestNotFound`` -> ``no_credentials`` (rule 3).
- A generic C2paError whose message starts with ``REMOTE_PREFIX`` ->
  ``remote_reference_only`` (rule 4), ONLY when the installed c2pa-python and
  SDK versions equal the pinned ones and remote fetch is disabled in the
  applied config. The prefix is quoted from the committed D1 output
  (eval/results/r1d1_library_outputs/remote_reference_jpg__production.json):
  ``Remote: must fetch remote manifests from url http://127.0.0.1:47811/...``.
  With other versions: ``error``, reason
  ``remote_reference_adapter_unverified_for_sdk_version``.
- Every other C2paError -> ``error`` (rule 2, ``c2pa_error``).
"""
import importlib.metadata
import io
import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from litmus.c2pa.settings import build_settings

PINNED_C2PA_PYTHON = "0.38.0"
PINNED_SDK = "0.91.0"
REMOTE_PREFIX = "Remote: must fetch remote manifests from url "


@dataclass
class ReadOutcome:
    kind: str  # store | no_credentials | remote_reference_only | error
    store: Optional[dict] = None
    reasons: List[str] = field(default_factory=list)
    detail: Optional[str] = None


def installed_versions() -> Tuple[str, str]:
    import c2pa

    return importlib.metadata.version("c2pa-python"), c2pa.sdk_version()


def classify_error(exc: Exception, config: Dict[str, Any],
                   versions: Tuple[str, str]) -> ReadOutcome:
    import c2pa

    if isinstance(exc, c2pa.C2paError.ManifestNotFound):
        return ReadOutcome("no_credentials", detail=str(exc))
    message = str(exc)
    if isinstance(exc, c2pa.C2paError) and message.startswith(REMOTE_PREFIX):
        if versions != (PINNED_C2PA_PYTHON, PINNED_SDK):
            return ReadOutcome(
                "error",
                reasons=["remote_reference_adapter_unverified_for_sdk_version"],
                detail=f"c2pa-python {versions[0]}, SDK {versions[1]}; adapter "
                       f"verified for {PINNED_C2PA_PYTHON} / {PINNED_SDK}")
        if (config.get("verify") or {}).get("remote_manifest_fetch") is not False:
            return ReadOutcome("error", reasons=["remote_fetch_not_disabled"],
                               detail=message)
        return ReadOutcome("remote_reference_only",
                           detail=message[len(REMOTE_PREFIX):])
    return ReadOutcome("error", detail=f"{type(exc).__name__}: {message}")


def read_store(data: bytes, mime: str, config: Dict[str, Any]) -> ReadOutcome:
    """Read one asset from memory with the given settings config."""
    import c2pa

    try:
        settings = build_settings(config)
    except Exception as e:
        return ReadOutcome("error", reasons=["c2pa_settings_rejected"],
                           detail=f"{type(e).__name__}: {e}")
    try:
        context = c2pa.Context(settings=settings)
        try:
            with io.BytesIO(data) as stream:
                with c2pa.Reader(mime, stream, context=context) as reader:
                    return ReadOutcome("store", store=json.loads(reader.json()))
        except c2pa.C2paError as e:
            return classify_error(e, config, installed_versions())
        finally:
            context.close()
    finally:
        settings.close()


@lru_cache(maxsize=1)
def supported_mime_types() -> Tuple[str, ...]:
    import c2pa

    return tuple(c2pa.Reader.get_supported_mime_types())
