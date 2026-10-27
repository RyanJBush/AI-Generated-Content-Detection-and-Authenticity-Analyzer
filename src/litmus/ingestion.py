import io
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image


class IngestionError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

# Constants
MAX_FILE_SIZE = 50_000_000
MAX_IMAGE_PIXELS = 50_000_000
MAX_DECODED_CHARS = 200_000
TEXT_EXTENSIONS = ('.txt', '.md')
# Extensions expected for each signature-detected type (SPEC 6.1.3 notes)
IMAGE_EXTENSIONS = {
    "image/jpeg": ('.jpg', '.jpeg'),
    "image/png": ('.png',),
    "image/webp": ('.webp',),
}

def _read_bytes(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()

def get_binary_signature(path: str, length: int = 16) -> bytes:
    with open(path, 'rb') as f:
        return f.read(length)

def _signature_mime(sig: bytes) -> Optional[str]:
    if sig.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    if sig.startswith(b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'):
        return "image/png"
    if sig.startswith(b'RIFF') and b'WEBP' in sig[:12]:
        return "image/webp"
    if sig.startswith(b'\x50\x4b\x03\x04'):
        return "application/zip"
    return None

def _detect_encoding(raw: bytes) -> Tuple[str, int]:
    """BOM detection: (codec, BOM length)."""
    if raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8', 3
    if raw.startswith(b'\xff\xfe'):
        return 'utf-16-le', 2
    if raw.startswith(b'\xfe\xff'):
        return 'utf-16-be', 2
    return 'utf-8', 0

def _decode_text(raw: bytes) -> Tuple[bool, str]:
    """Strict BOM-aware decode of already-read bytes (Addendum B2).

    Performs exactly one decode call. Returns (True, content) or (False, reason).
    """
    encoding, offset = _detect_encoding(raw)

    try:
        content = (raw[offset:] if offset else raw).decode(encoding)
    except UnicodeDecodeError:
        return False, "invalid encoding"

    if not content:
        return False, "empty_after_decoding"

    if '\0' in content:
        return False, "contains NUL"

    # Control char check (SPEC 6.1.2c)
    allowed = {'\t', '\n', '\r', '\f'}
    controls = [c for c in content if ord(c) < 32 and c not in allowed]
    if len(controls) / len(content) >= 0.01:
        return False, "too many control characters"

    # Max decoded text (SPEC 6.2)
    if len(content) > MAX_DECODED_CHARS:
        return False, "decoded text too large"

    return True, content

def _text_from_bytes(path: str, raw: bytes) -> Tuple[bool, str]:
    ext = os.path.splitext(path)[1].lower()
    if ext not in TEXT_EXTENSIONS:
        return False, "wrong extension"
    return _decode_text(raw)

def is_text_file(
    path: str, max_size: int = MAX_FILE_SIZE
) -> Tuple[bool, Optional[str]]:
    # size check before decoding
    size = os.path.getsize(path)
    if size > max_size:
        return False, "file too large"

    # extension check before reading
    ext = os.path.splitext(path)[1].lower()
    if ext not in TEXT_EXTENSIONS:
        return False, "wrong extension"

    try:
        return _decode_text(_read_bytes(path))
    except Exception as e:
        return False, str(e)

def detect_type(path: str) -> str:
    mime = _signature_mime(get_binary_signature(path))
    if mime is not None:
        return mime

    is_txt, _ = is_text_file(path)
    if is_txt:
        return "text/plain"

    return "not_supported"


@dataclass
class Ingested:
    """Outcome of ingesting one file; raw bytes and decoded text are reused."""
    result: str  # "supported" | "not_supported" | "error"
    reason: Optional[str] = None
    mime: Optional[str] = None
    size: int = 0
    raw: Optional[bytes] = None
    text: Optional[str] = None
    encoding: Optional[str] = None
    bom: bool = False
    image_size: Optional[Tuple[int, int]] = None
    notes: List[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.result == "supported"


def ingest(
    path: str, max_file_size: int = MAX_FILE_SIZE, max_pixels: int = MAX_IMAGE_PIXELS
) -> Ingested:
    size = os.path.getsize(path)

    # 0-byte check
    if size == 0:
        return Ingested("not_supported", "empty_input", size=size)

    # Global file size cap before anything else
    if size > max_file_size:
        return Ingested("not_supported", "file too large", size=size)

    # Read once; signature, image decode and text decode all reuse these bytes
    try:
        raw = _read_bytes(path)
    except OSError as e:
        return Ingested("error", f"read failed: {e}", size=size)

    mime = _signature_mime(raw[:16])

    if mime == "application/zip":
        return Ingested("not_supported", "documents arrive in R2",
                        mime=mime, size=size, raw=raw)

    if mime is not None:
        notes = []
        ext = os.path.splitext(path)[1].lower()
        if ext not in IMAGE_EXTENSIONS[mime]:
            notes.append(f"extension '{ext}' does not match content {mime}; "
                         "analyzed by content")
        try:
            with Image.open(io.BytesIO(raw)) as img:
                width, height = img.size
                if width * height > max_pixels:
                    return Ingested("not_supported", "image too large",
                                    mime=mime, size=size, raw=raw)
        except Exception as e:
            return Ingested("error", f"decode failed: {str(e)}",
                            mime=mime, size=size, raw=raw)
        return Ingested("supported", mime=mime, size=size, raw=raw,
                        image_size=(width, height), notes=notes)

    # Text path: decode once and reuse the decoded string (Addendum B2)
    is_txt, content = _text_from_bytes(path, raw)
    if not is_txt:
        return Ingested("not_supported", content or "unsupported format",
                        size=size, raw=raw)

    encoding, bom_len = _detect_encoding(raw)
    return Ingested("supported", mime="text/plain", size=size, raw=raw,
                    text=content, encoding=encoding, bom=bom_len > 0)


def analyze_ingestion(
    path: str, max_file_size: int = MAX_FILE_SIZE, max_pixels: int = MAX_IMAGE_PIXELS
) -> Dict[str, Any]:
    ing = ingest(path, max_file_size, max_pixels)

    if not ing.accepted:
        return {"result": ing.result, "reason": ing.reason}

    if ing.text is not None and not ing.text.strip():
        return {"result": "inconclusive", "reason": "no_nonwhitespace_content"}

    return {"result": "supported", "mime": ing.mime}
