"""Regenerate the committed CLI golden-test inputs in tests/fixtures/inputs.

Run once: python tests/fixtures/make_fixtures.py
The committed bytes, not this script, are what the golden tests hash;
image encoders may produce different bytes in other Pillow versions.
"""
import io
import pathlib
import zipfile

from PIL import Image

INPUTS = pathlib.Path(__file__).parent / "inputs"


def _image(fmt: str, color) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 6), color).save(buf, format=fmt)
    return buf.getvalue()


def _zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        info = zipfile.ZipInfo("a.txt", date_time=(2026, 1, 1, 0, 0, 0))
        z.writestr(info, b"zip member")
    return buf.getvalue()


FIXTURES = {
    "text.txt": "Litmus R0 golden fixture.\nSecond line, café.\n".encode("utf-8"),
    "whitespace.txt": b"  \n\t \r\n ",
    "empty.txt": b"",
    "bom_only.txt": b"\xef\xbb\xbf",
    "bad_utf8.txt": b"valid then \xff\xfe invalid",
    "image.jpg": _image("JPEG", (200, 30, 30)),
    "image.png": _image("PNG", (30, 200, 30)),
    "image.webp": _image("WEBP", (30, 30, 200)),
    "archive.zip": _zip(),
}


def main() -> None:
    INPUTS.mkdir(parents=True, exist_ok=True)
    for name, data in FIXTURES.items():
        (INPUTS / name).write_bytes(data)
        print(f"{name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
