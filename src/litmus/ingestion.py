import io
import os
from typing import Any, Dict, Optional, Tuple

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

def _decode_text(raw: bytes) -> Tuple[bool, str]:
    """Strict BOM-aware decode of already-read bytes (Addendum B2).

    Performs exactly one decode call. Returns (True, content) or (False, reason).
    """
    # BOM detection
    if raw.startswith(b'\xef\xbb\xbf'):
        encoding, offset = 'utf-8', 3
    elif raw.startswith(b'\xff\xfe'):
        encoding, offset = 'utf-16-le', 2
    elif raw.startswith(b'\xfe\xff'):
        encoding, offset = 'utf-16-be', 2
    else:
        encoding, offset = 'utf-8', 0

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

def analyze_ingestion(
    path: str, max_file_size: int = MAX_FILE_SIZE, max_pixels: int = MAX_IMAGE_PIXELS
) -> Dict[str, Any]:
    size = os.path.getsize(path)

    # 0-byte check
    if size == 0:
        return {"result": "not_supported", "reason": "empty_input"}

    # Global file size cap before anything else
    if size > max_file_size:
        return {"result": "not_supported", "reason": "file too large"}

    # Read once; signature, image decode and text decode all reuse these bytes
    try:
        raw = _read_bytes(path)
    except OSError as e:
        return {"result": "error", "reason": f"read failed: {e}"}

    mime = _signature_mime(raw[:16])

    if mime == "application/zip":
        return {"result": "not_supported", "reason": "documents arrive in R2"}

    if mime is not None:
        try:
            with Image.open(io.BytesIO(raw)) as img:
                width, height = img.size
                if width * height > max_pixels:
                    return {"result": "not_supported", "reason": "image too large"}
        except Exception as e:
            return {"result": "error", "reason": f"decode failed: {str(e)}"}
        return {"result": "supported", "mime": mime}

    # Text path: decode once and reuse the decoded string (Addendum B2)
    is_txt, content = _text_from_bytes(path, raw)
    if not is_txt:
        return {"result": "not_supported", "reason": content or "unsupported format"}

    if not content.strip():
        return {"result": "inconclusive", "reason": "no_nonwhitespace_content"}

    return {"result": "supported", "mime": "text/plain"}
