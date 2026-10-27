import builtins

from src.litmus import ingestion
from src.litmus.ingestion import analyze_ingestion


class CountingBytes(bytes):
    """bytes whose decode() calls are counted in a shared list."""

    decode_calls: list = []

    def decode(self, *args, **kwargs):
        CountingBytes.decode_calls.append((args, kwargs))
        return super().decode(*args, **kwargs)


class CountingFile:
    def __init__(self, real_file, reads):
        self._f = real_file
        self._reads = reads

    def read(self, *args):
        self._reads.append(args)
        return CountingBytes(self._f.read(*args))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._f.close()


def test_ingestion_reads_once_and_decodes_once(tmp_path, monkeypatch):
    path = tmp_path / "once.txt"
    path.write_bytes(b"Hello world, this is plain UTF-8 text.")

    opens = []
    reads = []
    CountingBytes.decode_calls = []

    def counting_open(file, mode="r", *args, **kwargs):
        opens.append((file, mode))
        return CountingFile(builtins.open(file, mode, *args, **kwargs), reads)

    # Shadow open() inside the ingestion module only
    monkeypatch.setattr(ingestion, "open", counting_open, raising=False)

    res = analyze_ingestion(str(path))

    assert res == {"result": "supported", "mime": "text/plain"}
    assert len(opens) == 1, f"expected 1 open, got {opens}"
    assert len(reads) == 1, f"expected 1 read, got {reads}"
    assert len(CountingBytes.decode_calls) == 1, (
        f"expected 1 decode, got {CountingBytes.decode_calls}"
    )
