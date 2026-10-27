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

## 2026-10-27 — Checkpoint R0-B (R0.4–R0.7)

All commit IDs below were checked with `git cat-file -t` and returned `commit`:
`6da2a6a` (R0-A accepted), `5f63b2e` (R0.5a), `18c7cbc` (R0.4), `53e5185` (R0.5b),
`95a6c5e` (R0.6).

### Backend

- `/status` provider and model lines: **not recorded.** The R0-B prompt again
  contained the unfilled placeholder `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`.
  As instructed, nothing is inferred from the agent's self-identification.

### R0.5a: package import (`5f63b2e`)

- The package is importable as `litmus` (src layout, editable install). Tests import
  `litmus`, not `src.litmus`. This resolves the R0-A known limitation:
  `pytest <repo>` run from `$HOME` passed (34 passed, exit 0) at that commit.
- **setuptools decision:** Ryan approved setuptools for R0-B as a build-only
  dependency. `setuptools==84.2.1` was installed into `.venv` and added to
  `requirements.lock`. The editable install used `--no-build-isolation`, so pip
  did not fetch any other build package. The `pip freeze --all` diff before and
  after the install showed only `setuptools==84.2.1` and the editable `litmus`.
  This extends Addendum B6's four-package list at Ryan's instruction.

### R0.4: offline evidence (`18c7cbc`)

API used for c2pa (installed c2pa-python 0.38.0, native SDK 0.91.0):
`Settings.set(path, value)` in `.venv/Lib/site-packages/c2pa/c2pa.py`
(`class Settings`, calling `c2pa_settings_set_value`), plus `Context(settings=...)`
and `Reader(format, stream, context=...)`. The deprecated `load_settings` was not used.

- **Settings presence (A1.4.4): UNVERIFIED by acceptance.** All four A1.2 settings
  are accepted. However, unknown keys (e.g. `verify.litmus_no_such_key`) are
  **also accepted silently**, so acceptance alone cannot show that a key exists.
  `test_c2pa_unknown_key_is_silently_accepted` records this behavior.
  - Supporting observation (does not change the status above): for each of the four
    keys, a wrong-type value is rejected with an error naming that key and its
    expected type (`expected a boolean` / `expected a sequence`). An unknown key
    accepts any type (`test_c2pa_offline_keys_are_type_checked`).
- **Claim type 1 — passes under network isolation: NOT RUN.** `docker --version`
  printed `Docker version 27.0.3, build 7d4bcd8` (exit 0), but `docker image ls`
  exited 1: `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the
  file specified.` The engine was not running, so no local image could be
  confirmed. Nothing was pulled.
- **Claim type 2 — zero attempted connections observed (trap with positive control):**
  - C2PA remote reference: a remote-reference fixture was produced locally
    without network access. It is a JPEG with no embedded manifest whose XMP
    `dcterms:provenance` points at the loopback trap. With the A1.2 settings,
    the trap recorded **0 connections**
    (`test_c2pa_remote_reference_zero_connections_with_offline_settings`;
    c2pa raises `must fetch remote manifests from url ...`).
  - Paired positive control (`test_c2pa_remote_reference_positive_control_reaches_trap`):
    with `verify.remote_manifest_fetch=true` and `core.allowed_network_hosts`
    holding only the trap's `host:port`, the trap recorded **1 connection**
    (`GET /manifest.c2pa`). The control passed, so the zero-connection result is
    valid for this fixture and configuration only. It does not cover other
    destinations, other formats, or other code paths.
  - Also observed: with fetch enabled and `core.allowed_network_hosts=[]`
    alone, the trap recorded 0 connections
    (`test_c2pa_empty_allowed_hosts_alone_blocks_fetch`).
  - Trap harness positive control for the Python path
    (`test_trap_positive_control_records_connection`): 1 connection recorded.
- Python socket guard (loopback only) and subprocess guard: tests in
  `tests/test_offline_guards.py` show non-loopback connects and lookups, and
  process launches, raise. `tests/test_cli_golden.py` shows both guards are
  active during `run_analysis`. These guards do not see native-library
  connections (Addendum A1.1).
- The C2PA analyzer stays **disabled** in R0 (R0-PLAN). No C2PA analysis results exist.

### R0.5b: CLI (`53e5185`)

- `litmus analyze FILE [-o PATH]` writes a report JSON with placeholder analyzers
  only. Golden tests cover text, whitespace-only, empty, BOM-only, bad UTF-8, JPEG,
  PNG, WebP and ZIP. The CLI ran from the repository root and from `$HOME`
  (exit 0 for reports, exit 1 for a missing file).

### R0.6: environment record (`95a6c5e`)

- `docs/environment.md` is generated by `scripts/gen_environment.py`.

### Not run in R0-B

- Network-isolation run (claim type 1): Docker engine not running (see above).
- Loopback UI test (A1.4.6): deferred to R1 by R0-PLAN.

## 2026-10-27 — R0-B corrections (on top of `b485cd7`)

`b485cd7` was checked with `git cat-file -t` and returned `commit`.

### Backend

- `/status` provider and model lines: **not recorded.** The prompt again contained
  the unfilled placeholder `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`.

### Fix 1: `-o` could overwrite the analyzed input

- **Bug (verified):** at `b485cd7`, `litmus analyze F -o F` exited 0 and replaced
  `F` with the report. The new tests in `tests/test_cli_output_safety.py` failed
  on that code with `assert 0 != 0`.
- **Fix:** before analysis, if the output path exists, the CLI rejects it when
  `os.path.samefile(input, output)` is true. Otherwise it rejects when the
  `normcase`d resolved paths are equal. Rejection exits 1, writes
  `litmus: refusing to overwrite the input file: ...` to stderr, and writes or
  modifies nothing.

### Fix 2: corrupt supported images were accepted

- **Bug (verified):** at `b485cd7`, ingestion only opened the header, so a
  half-truncated PNG or JPEG returned `supported`.
- **Fix:** the order is now (1) file-size limit, (2) header dimensions against
  the 50,000,000-pixel limit, before decoding, (3) a full `img.load()` with
  `ImageFile.LOAD_TRUNCATED_IMAGES` forced to `False` (also set `False` at
  import).
- **New reason code added in R0-B, PENDING REVIEW: `corrupt_image`.** It is
  returned as `{"result": "error", "reason": "corrupt_image"}` when the header
  parses but the full decode fails. The exception text goes into the ingestion
  notes.
- **Scope note:** a header that Pillow cannot open at all keeps the existing
  reason `decode failed: <exception>`. Truncated WebP falls in this group:
  Pillow 13.0.0's WebP plugin fails at open with `could not create decoder
  object`, so it returns `error` / `decode failed: ...`, not `corrupt_image`.
  Unifying the two codes is left for review.

### Still not run / disabled

- Network-isolation run: not run (Docker engine not running at R0-B).
- C2PA analysis: disabled (R0-PLAN).
