from src.litmus.ingestion import MAX_FILE_SIZE, MAX_IMAGE_PIXELS, analyze_ingestion


def create_file(dir, name, content=b""):
    path = dir / name
    path.write_bytes(content)
    return str(path)

def test_ingestion_encoding_and_bom(tmp_path):
    # UTF-8 with BOM
    path = create_file(tmp_path, "utf8bom.txt", b"\xef\xbb\xbfHello")
    assert analyze_ingestion(path) == {"result": "supported", "mime": "text/plain"}

    # UTF-16-LE with BOM
    path = create_file(tmp_path, "utf16le.txt", b"\xff\xfeH\x00e\x00l\x00l\x00o\x00")
    assert analyze_ingestion(path) == {"result": "supported", "mime": "text/plain"}

    # UTF-16-BE with BOM
    path = create_file(tmp_path, "utf16be.txt", b"\xfe\xff\x00H\x00e\x00l\x00l\x00o")
    assert analyze_ingestion(path) == {"result": "supported", "mime": "text/plain"}

    # BOM-only files
    path = create_file(tmp_path, "bomonly.txt", b"\xef\xbb\xbf")
    assert analyze_ingestion(path) == {
        "result": "not_supported", "reason": "empty_after_decoding"
    }

    # Invalid byte sequences
    path = create_file(tmp_path, "invalid.txt", b"Hello \xff World")
    assert analyze_ingestion(path)["result"] == "not_supported"

def test_ingestion_whitespace_encodings(tmp_path):
    # UTF-8 whitespace
    path = create_file(tmp_path, "ws_utf8.txt", b"  \n \t  ")
    assert analyze_ingestion(path) == {
        "result": "inconclusive", "reason": "no_nonwhitespace_content"
    }

    # UTF-16-LE whitespace
    path = create_file(tmp_path, "ws_utf16le.txt", b"\xff\xfe \x00 \x00\n\x00 \x00")
    assert analyze_ingestion(path) == {
        "result": "inconclusive", "reason": "no_nonwhitespace_content"
    }

def test_ingestion_control_char_boundary(tmp_path):
    # 100 chars, 1 control = 1% -> rejected
    content = b"a" * 99 + b"\x01"
    path = create_file(tmp_path, "ctrl_1pct.txt", content)
    assert analyze_ingestion(path) == {
        "result": "not_supported", "reason": "too many control characters"
    }

    # 101 chars, 1 control < 1% -> accepted
    content = b"a" * 100 + b"\x01"
    path = create_file(tmp_path, "ctrl_lt_1pct.txt", content)
    assert analyze_ingestion(path)["result"] == "supported"

def test_ingestion_limits_injectable(tmp_path):
    # File size limit
    path = create_file(tmp_path, "limit.txt", b"a" * 101)
    assert analyze_ingestion(path, max_file_size=100)["result"] == "not_supported"
    assert analyze_ingestion(path, max_file_size=101)["result"] == "supported"

    # Image pixel limit
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\x0d\x0a\x2d\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    path = create_file(tmp_path, "pixel.png", png_data)
    assert analyze_ingestion(path, max_pixels=0)["result"] == "not_supported"
    assert analyze_ingestion(path, max_pixels=1)["result"] == "supported"

def test_constants_value():
    assert MAX_FILE_SIZE == 50_000_000
    assert MAX_IMAGE_PIXELS == 50_000_000
