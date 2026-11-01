"""Explicit tokenizer-only slow check; no model constructors or weight access."""

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.slow
def test_pinned_local_tokenizer_without_weights_cuda_or_network():
    code = """
import json, pathlib, sys
from litmus.data_prep.guards import preparation_guards
from litmus.data_prep.text import load_local_tokenizer, assess
with preparation_guards() as attempts:
    tokenizer, identity = load_local_tokenizer(pathlib.Path(sys.argv[1]))
    observed, errors = assess('Independent tokenizer-only preparation probe. ' * 100,
                              tokenizer)
    assert not errors and observed['tokens_scored'] == 512
    assert 'torch' not in sys.modules
assert attempts == {'weight_file_access': 0, 'forbidden_import': 0, 'connections': 0}
print(json.dumps({'status': 'PASS', 'identity': identity, 'guards': attempts}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(ROOT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert '"status": "PASS"' in result.stdout
