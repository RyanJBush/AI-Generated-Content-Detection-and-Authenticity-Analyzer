import hashlib
import os
from typing import Tuple, Optional, Dict, Any
from PIL import Image
import io

class IngestionError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

def get_binary_signature(path: str, length: int = 16) -> bytes:
    with open(path, 'rb') as f:
        return f.read(length)

def is_text_file(path: str) -> Tuple[bool, Optional[str]]:
    # extension check
    ext = os.path.splitext(path)[1].lower()
    if ext not in ('.txt', '.md'):
        return False, "wrong extension"

    # size check (SPEC 6.2)
    size = os.path.getsize(path)
    if size > 50 * 1024 * 1024:
        return False, "file too large"

    # decode check
    try:
        with open(path, 'rb') as f:
            raw = f.read()

        # Handle BOM
        content = None
        if raw.startswith(b'\xef\xbb\xbf'):
            content = raw[3:].decode('utf-8')
        elif raw.startswith(b'\xff\xfe'):
            content = raw[2:].decode('utf-16-le')
        elif raw.startswith(b'\xfe\xff'):
            content = raw[2:].decode('utf-16-be')
        else:
            content = raw.decode('utf-8')

        if '\0' in content:
            return False, "contains NUL"

        # Control char check (SPEC 6.1.2c)
        # allowed: \t \n \r \f
        allowed = {'\t', '\n', '\r', '\f'}
        controls = [c for c in content if ord(c) < 32 and c not in allowed]
        if len(content) > 0 and len(controls) / len(content) >= 0.01:
            return False, "too many control characters"

        # Max decoded text (SPEC 6.2)
        if len(content) > 200000:
            return False, "decoded text too large"

        return True, None
    except UnicodeDecodeError:
        return False, "invalid encoding"
    except Exception as e:
        return False, str(e)

def detect_type(path: str) -> str:
    sig = get_binary_signature(path)

    # JPEG
    if sig.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    # PNG
    if sig.startswith(b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'):
        return "image/png"
    # WebP
    if sig.startswith(b'RIFF') and b'WEBP' in sig[:12]:
        return "image/webp"
    # ZIP (treated as container candidate, R0 rejects)
    if sig.startswith(b'\x50\x4b\x03\x04'):
        return "application/zip"

    # Signatureless text
    is_txt, reason = is_text_file(path)
    if is_txt:
        return "text/plain"

    return "not_supported"

def analyze_ingestion(path: str) -> Dict[str, Any]:
    # 0-byte check
    if os.path.getsize(path) == 0:
        return {"result": "not_supported", "reason": "empty_input"}

    mime = detect_type(path)

    if mime == "application/zip":
        return {"result": "not_supported", "reason": "documents arrive in R2"}

    if mime == "not_supported":
        # Attempt to find why it failed text check
        _, reason = is_text_file(path)
        return {"result": "not_supported", "reason": reason or "unsupported format"}

    if "image/" in mime:
        try:
            with Image.open(path) as img:
                width, height = img.size
                if width * height > 50 * 1024 * 1024: # 50MP
                    return {"result": "not_supported", "reason": "image too large"}
        except Exception as e:
            # For R0, if it's just a signature match but not a valid image file,
            # we report it as an error during decoding.
            return {"result": "error", "reason": f"decode failed: {str(e)}"}

    if mime == "text/plain":
        # Read for whitespace check (Addendum B2)
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if not content.strip():
                return {"result": "inconclusive", "reason": "no_nonwhitespace_content"}

    return {"result": "supported", "mime": mime}
