"""R0-B correction, Fix 2: corrupt supported images must not be accepted."""
import io
import struct
import zlib

import pytest
from PIL import Image, ImageFile

from litmus import ingestion
from litmus.ingestion import analyze_ingestion, ingest

FORMATS = [("PNG", "png", "image/png"), ("JPEG", "jpg", "image/jpeg"),
           ("WEBP", "webp", "image/webp")]


def _noise_image(fmt: str) -> bytes:
    # Noise keeps the compressed body large enough to truncate mid-data
    buf = io.BytesIO()
    Image.effect_noise((64, 64), 50).convert("RGB").save(buf, format=fmt)
    return buf.getvalue()


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_load_truncated_images_is_disabled():
    assert ImageFile.LOAD_TRUNCATED_IMAGES is False


@pytest.mark.parametrize("fmt, ext, mime", FORMATS)
def test_valid_images_still_accepted(tmp_path, fmt, ext, mime):
    path = _write(tmp_path, f"ok.{ext}", _noise_image(fmt))
    assert analyze_ingestion(path) == {"result": "supported", "mime": mime}


@pytest.mark.parametrize("fmt, ext", [("PNG", "png"), ("JPEG", "jpg")])
def test_truncated_png_jpeg_rejected_as_corrupt_image(tmp_path, fmt, ext):
    data = _noise_image(fmt)
    path = _write(tmp_path, f"trunc.{ext}", data[: len(data) // 2])
    # The header still parses, so only the full decode can catch this
    with Image.open(path) as img:
        assert img.size == (64, 64)
    assert analyze_ingestion(path) == {"result": "error", "reason": "corrupt_image"}


def test_truncated_webp_rejected_as_error(tmp_path):
    data = _noise_image("WEBP")
    path = _write(tmp_path, "trunc.webp", data[: len(data) // 2])
    # Pillow's WebP plugin already fails while opening a truncated file, so this
    # is caught at the header stage with the pre-existing "decode failed" reason.
    res = analyze_ingestion(path)
    assert res["result"] == "error"
    assert res["reason"].startswith("decode failed")


def _png_with_header_size(width: int, height: int) -> bytes:
    """A real 1x1 PNG whose IHDR claims width x height (CRC recomputed)."""
    buf = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buf, format="PNG")
    data = bytearray(buf.getvalue())
    # Signature (8) + length (4) + b"IHDR" (4), then width/height
    assert data[12:16] == b"IHDR"
    data[16:24] = struct.pack(">II", width, height)
    ihdr = bytes(data[12:29])  # type + 13 data bytes
    data[29:33] = struct.pack(">I", zlib.crc32(ihdr) & 0xFFFFFFFF)
    return bytes(data)


def test_over_limit_header_rejected_without_load(tmp_path, monkeypatch):
    # 8000 x 7000 = 56,000,000 > 50,000,000, below Pillow's own bomb limit
    path = _write(tmp_path, "huge.png", _png_with_header_size(8000, 7000))
    with Image.open(path) as img:
        assert img.size == (8000, 7000)

    def load_must_not_run(self, *args, **kwargs):
        raise AssertionError("load() called for an over-limit image")
    monkeypatch.setattr(Image.Image, "load", load_must_not_run)
    monkeypatch.setattr(ImageFile.ImageFile, "load", load_must_not_run)

    assert analyze_ingestion(path) == {"result": "not_supported",
                                       "reason": "image too large"}


def test_corrupt_image_keeps_detail_in_notes(tmp_path):
    data = _noise_image("PNG")
    ing = ingest(_write(tmp_path, "trunc.png", data[: len(data) // 2]))
    assert ing.result == "error" and ing.reason == "corrupt_image"
    assert any("truncated" in note for note in ing.notes)


def test_decode_forces_truncated_loading_off(tmp_path, monkeypatch):
    # Even if another component enables truncated loading, ingestion must not
    monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", True)
    data = _noise_image("PNG")
    path = _write(tmp_path, "trunc.png", data[: len(data) // 2])
    assert analyze_ingestion(path) == {"result": "error", "reason": "corrupt_image"}
    assert ImageFile.LOAD_TRUNCATED_IMAGES is True  # restored afterwards
    assert ingestion.MAX_IMAGE_PIXELS == 50_000_000
