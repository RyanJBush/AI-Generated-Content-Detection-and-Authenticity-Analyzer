import pytest
import os
import shutil
from src.litmus.ingestion import analyze_ingestion

@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path

def create_file(dir, name, content=b""):
    path = dir / name
    path.write_bytes(content)
    return str(path)

def test_ingestion_empty_file(temp_dir):
    path = create_file(temp_dir, "empty.txt", b"")
    res = analyze_ingestion(path)
    assert res == {"result": "not_supported", "reason": "empty_input"}

def test_ingestion_whitespace_only(temp_dir):
    path = create_file(temp_dir, "space.txt", b"   \n  \t  ")
    res = analyze_ingestion(path)
    assert res == {"result": "inconclusive", "reason": "no_nonwhitespace_content"}

def test_ingestion_bad_utf8(temp_dir):
    path = create_file(temp_dir, "bad.txt", b"hello \xff world")
    res = analyze_ingestion(path)
    assert res["result"] == "not_supported"
    assert "invalid encoding" in res["reason"]

def test_ingestion_nul_char(temp_dir):
    path = create_file(temp_dir, "nul.txt", b"hello\x00world")
    res = analyze_ingestion(path)
    assert res == {"result": "not_supported", "reason": "contains NUL"}

def test_ingestion_control_chars(temp_dir):
    # 1% threshold. 100 chars, 1 control char is exactly 1%.
    # Let's use 100 chars, 2 controls.
    content = b"a" * 98 + b"\x01\x02"
    path = create_file(temp_dir, "ctrl.txt", content)
    res = analyze_ingestion(path)
    assert res == {"result": "not_supported", "reason": "too many control characters"}

def test_ingestion_valid_text(temp_dir):
    path = create_file(temp_dir, "valid.txt", b"Hello world!")
    res = analyze_ingestion(path)
    assert res["result"] == "supported"
    assert res["mime"] == "text/plain"

def test_ingestion_wrong_extension(temp_dir):
    path = create_file(temp_dir, "valid.jpg", b"Hello world!") # Text content, wrong ext
    res = analyze_ingestion(path)
    # If it doesn't match a binary signature, it tries text rules.
    # But is_text_file checks extension.
    assert res["result"] == "not_supported"
    assert "wrong extension" in res["reason"]

def test_ingestion_zip_reject(temp_dir):
    # ZIP signature: 50 4B 03 04
    path = create_file(temp_dir, "test.zip", b"\x50\x4b\x03\x04\x00\x00\x00\x00")
    res = analyze_ingestion(path)
    assert res == {"result": "not_supported", "reason": "documents arrive in R2"}

def test_ingestion_image_signatures(temp_dir):
    # JPEG
    path = create_file(temp_dir, "test.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF")
    assert analyze_ingestion(path)["result"] == "supported"
    # PNG
    path = create_file(temp_dir, "test.png", b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a")
    assert analyze_ingestion(path)["result"] == "supported"
    # WebP
    path = create_file(temp_dir, "test.webp", b"RIFF\x00\x00\x00\x00WEBP")
    assert analyze_ingestion(path)["result"] == "supported"

def test_ingestion_image_too_large(temp_dir):
    # We can't easily create a 50MP image without lots of memory,
    # but we can mock the Pillow open or just test the 50MB file size limit.
    # 50MB + 1 byte
    path = create_file(temp_dir, "big.txt", b"a" * (50 * 1024 * 1024 + 1))
    res = analyze_ingestion(path)
    assert res == {"result": "not_supported", "reason": "file too large"}
