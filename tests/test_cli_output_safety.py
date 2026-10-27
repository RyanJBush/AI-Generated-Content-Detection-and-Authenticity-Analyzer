"""R0-B correction, Fix 1: `-o` must never overwrite the analyzed input."""
import hashlib
import json
import os

import pytest

from litmus.cli import main

CONTENT = b"Input that must never be overwritten.\n"


def _sha(path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture
def victim(tmp_path):
    path = tmp_path / "input.txt"
    path.write_bytes(CONTENT)
    return path


def _assert_rejected(capsys, victim, argv):
    before = _sha(victim)
    code = main(argv)
    captured = capsys.readouterr()
    assert code != 0
    assert "refusing to overwrite the input file" in captured.err
    assert captured.out == ""
    assert _sha(victim) == before
    assert victim.read_bytes() == CONTENT


def test_output_same_path_string_rejected(capsys, victim):
    _assert_rejected(capsys, victim, ["analyze", str(victim), "-o", str(victim)])


def test_output_relative_vs_absolute_rejected(capsys, victim, monkeypatch):
    monkeypatch.chdir(victim.parent)
    _assert_rejected(capsys, victim,
                     ["analyze", victim.name, "-o", str(victim.resolve())])
    _assert_rejected(capsys, victim,
                     ["analyze", str(victim.resolve()), "-o", victim.name])


def test_output_dotdot_path_rejected(capsys, victim):
    sub = victim.parent / "sub"
    sub.mkdir()
    dotdot = os.path.join(str(sub), "..", victim.name)
    assert dotdot != str(victim)
    _assert_rejected(capsys, victim, ["analyze", str(victim), "-o", dotdot])


def test_output_hard_link_rejected(capsys, victim):
    link = victim.parent / "hardlink.txt"
    # Must fail (not skip) if the link cannot be created
    os.link(victim, link)
    assert os.path.samefile(victim, link)
    _assert_rejected(capsys, victim, ["analyze", str(victim), "-o", str(link)])
    assert link.read_bytes() == CONTENT


def test_output_distinct_path_still_written(capsys, victim, tmp_path):
    out = tmp_path / "report.json"
    before = _sha(victim)
    code = main(["analyze", str(victim), "-o", str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "" and captured.err == ""
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["input"]["file_name"] == "input.txt"
    assert report["input"]["sha256"] == before
    assert _sha(victim) == before

    # Existing distinct output file is overwritten as before
    code = main(["analyze", str(victim), "-o", str(out)])
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8")) == report
