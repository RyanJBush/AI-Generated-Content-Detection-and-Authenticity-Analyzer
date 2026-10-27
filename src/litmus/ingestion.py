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

def get_binary_signature(path: str, length: int = 16) -> bytes:
    with open(path, 'rb') as f:
        return f.read(length)

def is_text_file(
    path: str, max_size: int = MAX_FILE_SIZE
) -> Tuple[bool, Optional[str]]:
    # size check before decoding
    size = os.path.getsize(path)
    if size > max_size:
        return False, "file too large"

    # extension check
    ext = os.path.splitext(path)[1].lower()
    if ext not in ('.txt', '.md'):
        return False, "wrong extension"

    try:
        with open(path, 'rb') as f:
            raw = f.read()

        # BOM detection and strict decode
        content = None
        if raw.startswith(b'\xef\xbb\xbf'):
            content = raw[3:].decode('utf-8')
        elif raw.startswith(b'\xff\xfe'):
            content = raw[2:].decode('utf-16-le')
        elif raw.startswith(b'\xfe\xff'):
            content = raw[2:].decode('utf-16-be')
        else:
            content = raw.decode('utf-8')

        if not content:
            return False, "empty_after_decoding"

        if '\0' in content:
            return False, "contains NUL"

        # Control char check (SPEC 6.1.2c)
        allowed = {'\t', '\n', '\r', '\f'}
        controls = [c for c in content if ord(c) < 32 and c not in allowed]
        if len(content) > 0 and len(controls) / len(content) >= 0.01:
            return False, "too many control characters"

        # Max decoded text (SPEC 6.2)
        if len(content) > 200000:
            return False, "decoded text too large"

        return True, content
    except UnicodeDecodeError:
        return False, "invalid encoding"
    except Exception as e:
        return False, str(e)

def detect_type(path: str) -> str:
    sig = get_binary_signature(path)

    if sig.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    if sig.startswith(b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'):
        return "image/png"
    if sig.startswith(b'RIFF') and b'WEBP' in sig[:12]:
        return "image/webp"
    if sig.startswith(b'\x50\x4b\x03\x04'):
        return "application/zip"

    is_txt, reason = is_text_file(path)
    if is_txt:
        return "text/plain"

    return "not_supported"

def analyze_ingestion(
    path: str, max_file_size: int = MAX_FILE_SIZE, max_pixels: int = MAX_IMAGE_PIXELS
) -> Dict[str, Any]:
    # 0-byte check
    if os.path.getsize(path) == 0:
        return {"result": "not_supported", "reason": "empty_input"}

    # Global file size cap before anything else
    if os.path.getsize(path) > max_file_size:
        return {"result": "not_supported", "reason": "file too large"}

    mime = detect_type(path)

    if mime == "application/zip":
        return {"result": "not_supported", "reason": "documents arrive in R2"}

    if mime == "not_supported":
        _, reason = is_text_file(path, max_size=max_file_size)
        return {"result": "not_supported", "reason": reason or "unsupported format"}

    if "image/" in mime:
        try:
            with Image.open(path) as img:
                width, height = img.size
                if width * height > max_pixels:
                    return {"result": "not_supported", "reason": "image too large"}
        except Exception as e:
            return {"result": "error", "reason": f"decode failed: {str(e)}"}

    if mime == "text/plain":
        # Use strict decode from is_text_file (Addendum B2)
        is_txt, content = is_text_file(path)
        if is_txt and content and not content.strip():
            return {"result": "inconclusive", "reason": "no_nonwhitespace_content"}


    return {"result": "supported", "mime": mime}
