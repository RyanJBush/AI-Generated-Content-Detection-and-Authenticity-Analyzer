import pytest
from src.litmus.ingestion import analyze_ingestion
import os

def create_file(dir, name, content=b""):
    path = dir / name
    path.write_bytes(content)
    return str(path)

def test_ingestion_image_decode_error(tmp_path):
    # Valid signature, but invalid image data
    path = create_file(tmp_path, "corrupt.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"not a real image")
    res = analyze_ingestion(path)
    assert res["result"] == "error"
    assert "decode failed" in res["reason"]

def test_ingestion_image_supported_signatures(tmp_path):
    # Smallest valid PNG (1x1 transparent)
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\x0d\x0a\x2d\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    path = create_file(tmp_path, "pixel.png", png_data)
    res = analyze_ingestion(path)
    assert res["result"] == "supported"
    assert res["mime"] == "image/png"
