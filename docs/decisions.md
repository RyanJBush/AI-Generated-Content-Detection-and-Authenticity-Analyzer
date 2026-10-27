# Decisions and Corrections Log

Append-only. Do not delete or rewrite earlier entries; add a dated correction instead.

## 2026-10-27 — R0-A Correction 2

### Backend

- `/status` provider and model lines: **not recorded.** The R0-A Correction 2
  continuation prompt contained the unfilled placeholder
  `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`, so no `/status` output
  was supplied to the agent.
- The agent's self-reported model ID, read from its own runtime configuration (not from `/status`):
  `claude-opus-5-5` (Claude Code).
- The earlier, interrupted Correction 2 session ran on a different backend
  (Ollama, per Ryan). Its uncommitted changes were kept and reviewed, not taken as already verified.

### Correction: false "Ruff clean" claim in 4dae474

- Commit `4dae474` ("R0-A: Corrected Checkpoint") states "Verified Ruff linting
  is clean." **That claim was false.** Running
  `ruff check --config pyproject.toml src tests` on a `git archive 4dae474`
  extraction on 2026-10-27 exited 1 with `Found 14 errors.` (E501 x10, I001 x2,
  F401 x2, F841 x1 in `tests/test_tree_atomicity.py`).
- The same commit says ingestion uses "a single strict pass." **That was also
  false.** At `4dae474`, `analyze_ingestion` opened a valid `.txt` file 3 times
  (signature read plus two full `is_text_file` reads/decodes), as measured by
  `tests/test_fix5_decode_once.py` run against the 4dae474 source.
- The commit message is left unchanged (no history rewriting). This entry is the correction.

### Fixes in this correction

1. Ruff clean under the unchanged `pyproject.toml` (code fixed, config not weakened).
2. `QualityObservation.status` is now a `QualityStatus` enum; invalid values are
   rejected via both `from_json` and direct construction.
3. `SegmentTree.validate` returns False for a dangling `parent_id`.
4. `test_tree_cycle_atomicity` asserts rejection of cycle-creating additions and
   compares serialized state before and after.
5. `analyze_ingestion` reads the file once and decodes once (images are decoded
   from the same bytes via `io.BytesIO`).
6. `test_ingestion_image_signatures` is now a real parametrized test (PNG, JPEG,
   WEBP); no skipped tests remain.

### Known limitation (not changed in this correction)

- Tests import the package as `src.litmus` and there is no `pythonpath` /
  conftest setup. `pytest` invoked from outside the repository root fails at
  collection with `ModuleNotFoundError: No module named 'src'`. Run from the
  repository root until packaging is addressed.
