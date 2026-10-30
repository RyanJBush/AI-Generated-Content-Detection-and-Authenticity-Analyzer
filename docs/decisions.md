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

## 2026-10-27 — R1 planning and R1-A authorization

`13f6a2d` (R0 closed) was checked with `git cat-file -t` and returned `commit`.

### Backend

- `/status` provider and model lines: **not recorded.** The R1-A prompt again
  contained the unfilled placeholder `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`.

### Plan files

- `R1-PLAN.md` SHA-256 `71214e83190398f9d3072ed163a83a053a674c1302d846c8ec3d566f3b317617`
  and `R1-PLAN-CORRECTIONS-A.md` SHA-256
  `65f3b6fdf84ead3c359dd01fdab3712bf5cdce1d681daaea0cff21249e33314a` both match
  the values in the R1-A instruction. The files were supplied in `~/Downloads`
  (not in the repository) and copied byte-for-byte. Both are marked `-text` in
  `.gitattributes` so Git does not convert their line endings.

### Authorization (Ryan, as stated in the R1-A instruction)

- R1-PLAN v2 approved as the roadmap.
- **R1-A authorized:** `torch` and `transformers` in the project `.venv`, with the
  transitive dependencies they require recorded and pinned (CA3). Any additional
  top-level package needs a separate decision.
- The two specified Qwen revisions: `Qwen/Qwen2.5-0.5B @ 060db6499f32faf8b98477b0a26969ef7d8b9987`
  and `Qwen/Qwen2.5-0.5B-Instruct @ 7ae557604adf67be50417f59c2c2f167def9a775`.
- Retired-math option (a) is approved **for use in R1-B**. Retired files are not
  consulted in R1-A.
- **Not authorized:** R1-B and later, and RAID acquisition.
- Precedence: R1-PLAN-CORRECTIONS-A.md > R1-PLAN.md > Addendum B > Addendum A > SPEC.md.

## 2026-10-27 — Checkpoint R1-A outcomes

Commits checked with `git cat-file -t` (all `commit`): `3b0db47` (planning),
`2041bc5` (dependencies), `7680d20` (model setup).

### Dependencies (`2041bc5`)

- `torch==2.6.0+cu124` from `https://download.pytorch.org/whl/cu124`, and
  `transformers==4.57.6` with no extras.
- **Why 4.57.6:** its metadata declares `torch>=2.2` (via the `torch` extra),
  whereas 5.21.0 declares `torch>=2.6`, putting torch 2.6.0 at its floor. A
  `--dry-run` showed 4.57.6 adds 8 packages and 5.21.0 adds 20.
- The `transformers[torch]` extra was not installed, because it would add
  `accelerate`, a separate top-level package under CA3.
- 17 new packages: 2 top-level (torch, transformers) and 15 transitive. Each
  `Required-by` chain was checked with `pip show` and recorded in
  `requirements.lock`. `pip check`: `No broken requirements found.`

### Models (`7680d20`)

- `model.safetensors` SHA-256 matched the published values for both pinned
  revisions. The hashes of all downloaded files are in `models.manifest.json`.
  The weights are in git-ignored `models/`.

### Tokenizer checks (`eval/results/r1a_tokenizer_checks.json`)

- **Equality:** `tokenizer.json` is identical in both repos (SHA-256
  `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539`). The full
  vocabularies (151,665 entries) and the added-token tables are equal. The
  `special_tokens_map` differs (`eos_token`: `<|endoftext|>` in the base model,
  `<|im_end|>` in Instruct).
- **Agreement:** token IDs are identical between the two models for every
  probe. `add_special_tokens` (omitted / True / False) never changed IDs on
  these fixtures.
- **split_special_tokens:** it changed IDs only for the literal-special-token
  fixture. With `False`, `<|endoftext|>`, `<|im_end|>` and `<|im_start|>`
  became control IDs 151643, 151645 and 151644; with `True` they were tokenized
  as text.
- **PROPOSED, not final:** `split_special_tokens = True`, `add_special_tokens = False`.

### Offline load (A1.4.2 + B4): claim type 2 only

- **Zero attempted connections observed, with a passing positive control.**
  - With `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` and `HF_ENDPOINT` set to
    the loopback trap, both tokenizers and both models loaded from `models/`
    with `local_files_only=True`. The trap recorded 0 connections.
  - Control: with offline mode off and the same `HF_ENDPOINT`, one `model_info`
    call reached the trap: 1 connection, `GET /api/models/Qwen/Qwen2.5-0.5B`.
  - This covers this load path and the HF endpoint only.
- **Claim type 1 (network isolation): NOT RUN.** Docker isolation stays not run.

### Compatibility smoke (`eval/results/r1a_smoke.json`; not the scorer)

- **Run:** CUDA, fp32, batch size 1, 200 tokens. Logits were finite for both
  models; vocabulary dimension 151936 for both; dtype `torch.float32` on
  `cuda:0`. Peak `torch.cuda.max_memory_allocated` was 4298951680 bytes with
  both models loaded.
- **Execution profile:** RTX 4060 Laptop GPU, driver 572.60, CUDA runtime 12.4,
  torch 2.6.0+cu124, transformers 4.57.6, `matmul.allow_tf32=False`,
  `cudnn.allow_tf32=True`, float32 matmul precision `highest`, deterministic
  algorithms off, Windows. Profile complete.
- No Binoculars score was computed.

## 2026-10-28 — Checkpoint R1-B1 (scorer, uncalibrated)

`357ac92` (R1-A accepted) was checked with `git cat-file -t` and returned `commit`.

### Backend routing: UNVERIFIED

- The provider and model routing for this session is **unverified**. Ryan has
  not supplied actual `/status` output. Nothing is inferred from the agent's
  self-identification.

### Authorization (Ryan, as stated in the R1-B1 instruction)

- Preprocessing policy: `add_special_tokens=False`, `split_special_tokens=True`.
  This finalizes the R1-A proposal.
- Numerical settings: `attn_implementation="eager"`; TF32 off for matmul and
  cuDNN; float32 matmul precision `"highest"`.
- Retired-math option (a): read-only consultation via `git show`.

### Retired files read (option a)

- Read with `git show litmus-text-before-multimodal-2026-10-26:<path>`. The tag
  resolves to commit `106a645`.
  - `src/litmus/binoculars.py`
  - `tests/test_binoculars_math.py`
- **Ported:** the A4 statistics (shifted performer NLL, all-position XENT,
  float32 log-softmax and reductions, validation guards), reduced to batch size
  1 with no mask; and the hand-computed power-of-2 vectors (main fixture, role
  swap, first/last token, final-position, zero-XENT, validator cases).
- **Not ported:** batching, attention masks and padding (A4 fixes batch size 1);
  `nll_observer` (not an A4 quantity). No file was restored or checked out.

### Deterministic-algorithm choice

- `torch.use_deterministic_algorithms(True)` with
  `CUBLAS_WORKSPACE_CONFIG=":4096:8"` (set before CUDA initialization).
- Read back as `True` and `":4096:8"`.
- Two runs on the same text gave an identical `raw_score` in the slow suite.

### Implementation choices for review

- **NVIDIA driver:** read through NVML via `ctypes`, because analysis runs under
  the subprocess guard and `nvidia-smi` would be blocked. Read back `572.60`,
  the same value `nvidia-smi` reported in R1-A.
- **Opt-in detector:** `litmus analyze` keeps the R0 placeholder by default. The
  scorer is used with `--text-origin binoculars`, so the R0 golden files are
  unchanged.
- **Weights not re-hashed at load:** the loader checks that the model files
  exist and that `tokenizer.json`'s SHA-256 matches. Weight hashes are verified
  by the setup script and the R1-A slow test, not at every load.

### Bug found and fixed before commit

- In a draft report, `torch_version` serialized as `{}`. `torch.__version__` is
  a `str` subclass with a `__dict__`, and `schemas.to_json` treated it as an
  object. The hash input (via `json.dumps`) was not affected.
- **Fix:** profile values are cast to `str`, and `to_json` keeps `str`
  subclasses as text.
- **Regression tests:** a default-suite test for `to_json`, and a slow test
  checking that the reported `scoring_config` re-hashes to the reported
  `scoring_config_hash`.

### Not in R1-B1

- No timing or memory measurement (R1-B2).
- No calibration and no threshold application (R1-F).
- No RAID data.
- C2PA analysis stays disabled; quality observers are not implemented.
- Docker isolation: not run.

## 2026-10-29 — R1-B1 corrections (on top of `6ca2b43`)

`6ca2b43` was checked with `git cat-file -t` and returned `commit`.

### Backend routing: still UNVERIFIED

- The correction instruction asks for Ryan's `/status` provider and model lines
  to replace the R1-B1 note, but its backend line is still the unfilled
  placeholder `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`.
- Nothing to record verbatim, so the R1-B1 note stands: routing is
  **unverified**, and nothing is inferred from the agent's self-identification.

### Fix 1: explicit profile completeness

- `PROFILE_SCHEMA` / `profile_failures()` in `scorer/loader.py` replace the
  former "no value equals `unavailable`" check. The schema is in
  `docs/interfaces.md`.
- `cublas_workspace_config` counts as a GPU-specific field: on CPU it is now
  read back as `not_applicable` and must be `not_applicable`. CPU runs stay
  uncalibrated.

### Fix 2: source identity

- `scorer/analyzer.py` and `scorer/identity.py` added to the hashed source list
  (7 files).
- Not changed, report only: `scorer/calibration.py` (see the R1-B1 corrections
  report).

### Fix 3: settings before CUDA initialization

- `configure_numerics(device_type)` replaces `apply_numerical_settings()`.
  `load_pair` chooses the device (`torch.cuda.is_available()` does not
  initialize CUDA) and then configures, before any model or tensor touches the
  device.
- `CUBLAS_WORKSPACE_CONFIG` is now set (overwritten) only for CUDA. Before, it
  was `setdefault` for every device.
- New hashed profile field `cuda_initialized_before_settings`. The golden test
  hash was recomputed and cross-checked with `sha256sum`.
- The analyzer no longer re-applies settings before scoring, since re-applying
  would hide a change. It re-reads them and refuses to score on any
  difference (`execution_profile_changed`).
- torch couples `matmul.allow_tf32` and `float32_matmul_precision`: changing one
  changes the other, so a change to either one reports both fields.

### Not in the R1-B1 corrections

- No RAID access, no calibration, no R1-B2 benchmarking.

## 2026-10-30 — Checkpoint R1-B2 (synthetic runtime and GPU-memory benchmark)

`9a32191` (R1-B1 closed) was checked with `git cat-file -t` and returned `commit`.

### Backend routing: still UNVERIFIED

- The R1-B2 instruction's backend line is the unfilled placeholder
  `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`. There is nothing to record
  verbatim, so routing stays **unverified**. Nothing is inferred from the
  agent's self-identification.

### Preconditions (log: `eval/results/logs/r1b2_preflight.log`)

- HEAD was `9a32191` and the tree was clean.
- `nvidia-smi` showed no running processes. The compute-apps query returned the
  header only. `ollama ps` listed no loaded model.
- AC power `Online` (battery charging), power plan `Balanced`
  (`381b4222-f694-41f0-9685-ff5bb260df2e`).
- In a fresh process, the execution profile validated as complete
  (`profile_failures == {}`), with `cuda_initialized_before_settings = false`.
  `scoring_config_hash` was `eb2db0e9d79c6d4e4b119a4466e901ee5264344e0ed516ea0777cc4222d0ab97`.

### Inputs and method

- `scripts/r1b2_inputs.py` generates 10 seeded word-salad texts at each of 64,
  128, 256 and 512 tokens (base seed 20261030), using a built-in word list and
  no dataset text.
- Each text was re-tokenized after writing (production `tokenize_window`) and
  has exactly its target count. SHA-256 values are in
  `eval/inputs/r1b2/manifest.json`. A logged regeneration produced
  byte-identical files.
- `scripts/benchmark_r1b2.py` calls the production functions (`load_pair`,
  `forward_logits`, `binoculars_statistics`, `BinocularsAnalyzer`). Definitions
  are recorded in the results JSON.
- The run used 5 untimed warmup scoring calls per length, then 3 timed passes
  over 10 texts (30 timed calls per length and phase). Each length block ran
  under `offline_guards()`.
- An earlier unlogged dry run, written to a scratch directory, checked that the
  script works. Its numbers are not used.

### Measured results (`eval/results/r1b2_benchmark.json`; log `eval/results/logs/r1b2_benchmark.log`)

All times are in milliseconds, n = 30 per cell. p90 is the nearest-rank p90.

| Tokens | Tokenization min/median/p90 | Scoring min/median/p90 | End-to-end min/median/p90 | Peak allocated | Peak reserved |
|---|---|---|---|---|---|
| 64  | 0.20 / 0.23 / 0.26 | 43.82 / 48.84 / 57.13 | 45.28 / 49.84 / 58.10 | 4,226,335,744 B | 4,469,030,912 B |
| 128 | 0.31 / 0.34 / 0.37 | 52.56 / 55.92 / 60.26 | 55.36 / 56.68 / 60.76 | 4,454,008,320 B | 4,951,375,872 B |
| 256 | 0.51 / 0.54 / 0.58 | 99.54 / 101.57 / 111.80 | 100.63 / 103.18 / 114.97 | 4,920,756,736 B | 5,899,288,576 B |
| 512 | 0.88 / 0.93 / 1.02 | 203.13 / 214.90 / 226.43 | 205.00 / 218.49 / 225.47 | 5,854,253,568 B | 7,774,142,464 B |

- **Model load, 3 fresh processes:** 4.006 s, 3.690 s, 3.712 s. The measuring
  process's own load took 3.651 s. Imports of torch and transformers were timed
  separately (about 2.3 s per process).
- **Memory:** allocated after load 3,953,704,960 B, reserved after load
  4,194,304,000 B. Total VRAM 8,585,216,000 B. Peak reserved at 512 tokens is
  about 90.6% of total VRAM.
- **Errors and consistency:** 0 scorer errors and 0 guard failures. Every text
  gave a single distinct score across all its scoring and end-to-end calls.
  Every end-to-end result was `inconclusive` / `no calibration for this
  configuration`.
- **File cache:** the model files had been read minutes earlier (Step 0 and the
  dry run), so all four loads are warm-cache loads. A cold-cache load was not
  measured.
- **GPU clocks:** the SM clock fell from 2625 MHz before the 64-token block to
  2010–2190 MHz in the later blocks, with temperature 47–67 °C and power up to
  79.75 W of the 80 W cap (nvidia-smi samples between blocks). This was not
  controlled.

### ESTIMATE: sample size (not measured; every number below is an ESTIMATE)

- **Per-text cost:** `c` = measured end-to-end p90 at 512 tokens = 0.22547 s
  (ESTIMATE, applied to every RAID text). This is a planning estimate, not an
  upper bound. RAID lengths are UNMEASURED.
- **Unmeasured costs (R1-B2 corrections):**
  - Production tokenizes the full decoded input before truncating to 512
    tokens, so tokenization cost for long inputs (up to the 200,000-code-point
    limit, `MAX_DECODED_CHARS`) is unmeasured. The benchmark's longest input
    was 512 tokens (2,995 characters).
  - Sustained thermal effects over multi-hour runs are unmeasured. The 56 s run
    already showed SM clock reductions (2625 → 2010–2190 MHz) and power near
    the 80 W limit (up to 79.75 W).
  - A cold-cache model load is unmeasured; all measured loads were warm-cache.
  - Dataset processing overhead is unmeasured: reading, decoding,
    deduplication and manifest work.
- **Per group:** `k` texts, with `k = 2` clean-only (1 human + 1 machine) or
  `k = 5` with 3 attacked variants. Scoring time is `T(G) = G · k · c`, plus one
  model load `L` (measured maximum 4.006 s).
- **Groups for a budget `B`:** `G = floor(B / (k · c))` (ESTIMATE):

| Scoring budget B | Clean-only (k=2) | Clean + attacks (k=5) |
|---|---|---|
| 0.5 h | 3,991 | 1,596 |
| 1 h | 7,983 | 3,193 |
| 2 h | 15,966 | 6,386 |
| 4 h | 31,933 | 12,773 |

- **Development allocation:** the 30% development share is EXPECTED, not
  guaranteed. It is a hash-based assignment, so the realized share for a given
  G can differ from 0.3.
- **Calibration rule:** the 5% calibration is enabled only if at least 200
  ELIGIBLE development human texts remain after all exclusions (deduplication,
  eligibility, pair cleanup). Otherwise no calibration is created.
- **Design lower bound:** expected dev human texts = 0.3 · G ≥ 200, so G ≥ 667.
  An ASSUMED 20% exclusion margin (too_short, missing variants, errors), which
  is not measured, gives G ≥ 834 (ESTIMATE). Neither figure guarantees 200
  eligible development human texts. The calibration rule above decides that.
- **N_target status: APPROVED** (was PROPOSED; see "2026-10-30 — N_target
  approval and R1-B2 closure" below). N_target = 1,000
  groups (an expected 300 dev human texts). Clean + attacks is 5,000 texts, for
  an ESTIMATE of 1,127 s (18.8 min) scoring plus about 4 s load. This fits the
  0.5 h candidate budget with about 1.6× headroom. Clean-only is an ESTIMATE
  of 7.5 min.
- **Approval requirement:** Ryan's approval must be recorded in
  `docs/decisions.md`, with the date of the approving message, before any
  dataset selection begins.

### R1-B2 corrections (documentation and test markers)

- The five benchmark-input tests that load the real tokenizer from `models/` are
  now marked slow. The generator stand-in tests and the manifest/hash test stay
  in the default suite.
- **Wording-only changes to the R1-B2 ESTIMATE section above:**
  - "planning estimate, not an upper bound" for c.
  - The unmeasured-cost list.
  - The dev-allocation and calibration-enablement rule.
  - The N_target status.
  - No measured value changed.
- `eval/results/r1b2_benchmark.json` is unchanged. It has no recommendation
  section: the ESTIMATE section was kept out of the measurement file and lives
  only here.
- **Backend routing:** still UNVERIFIED. The correction instruction's backend
  line is the unfilled placeholder.

### Not in R1-B2

- No RAID acquisition, no calibration, no quality observers, no C2PA work.
- Docker isolation: not run.

## 2026-10-30 — N_target approval and R1-B2 closure

- **2026-10-30: Ryan approved N_target = 1,000 source groups for R1-E dataset
  selection.** This approval comes from Ryan's instruction message of
  2026-10-30. It updates the N_target entry in the R1-B2 ESTIMATE section from
  PROPOSED to APPROVED. The per-group cost and time figures there remain
  ESTIMATES.
- **2026-10-30: R1-B2 closed.** Independent review (Codex) accepted correction
  commit `82a2eca`: 298 default tests passed with model-file reads blocked and
  zero attempted accesses; Ruff passed. Ryan's terminal: 19 slow tests passed.
  - These results were reported by the reviewer and by Ryan. They are recorded
    as reported and were not run by the agent for this entry.
- **Reminder:** R1-E still requires Ryan's separate approval for RAID
  acquisition. N_target approval is not acquisition approval.
- **Backend routing:** still UNVERIFIED. The instruction's backend line is the
  unfilled placeholder.

## 2026-10-30 — R1-C plan approval

`2b52db7` was checked with `git cat-file -t` and returned `commit`.

**2026-10-30: Ryan approved the R1-C plan at 2b52db7.** Recorded from Ryan's instruction message of 2026-10-30.

- **The ten §h.1 recommendations are APPROVED:**
  1. Ship all four observers with the small lexicons.
  2. Omit `may` from `hedges`.
  3. Contractions match only when listed.
  4. Leftmost-longest, non-overlapping matching within each observer.
  5. Lexicon SHA-256 and observer version in `notes` (fixed format, no schema change).
  6. No stop-word filtering.
  7. Word 3-grams may cross punctuation and line breaks.
  8. Spans capped at 1,000 per observer, with an exact count and truncation reported in `notes`.
  9. Opt-in via `--quality {off,on}`, default `off`.
  10. Image segments keep `quality: []`.
- **Lexicon entries:** the entries proposed in the plan are approved as **provisional v1**.
- **Attribution:** the lexicons were drafted with AI assistance (Claude Code) for the Litmus project and reviewed by Ryan.
- **Licensing:** the repository and lexicon licenses remain "OPEN — pending Ryan's decision". No license has been chosen or applied.
- **Performance:** 5 s per 200,000 code points is a benchmark target. If it is exceeded, the measurements and the cause are reported for review before R1-C closes.
- **Language:** the language and word-count limitations are kept. There is no language-detection feature.
- **`--quality` default:** the default after R1-H is deferred to R1-H.
- **Plan adjustments:**
  1. C1 import-isolation checks cover only C1 components. Constructing and running all four observers is checked in C2.
  2. Installed-wheel verification uses a unique temporary directory and an assertion script that exits nonzero on failure (plan §j).
- **Plan status:** "APPROVED 2026-10-30 (at 2b52db7), with adjustments recorded in docs/decisions.md".
- **Backend routing:** still UNVERIFIED. No `/status` output has been supplied.

## 2026-10-30 — Checkpoint R1-C1 (lexicons, loader, word index, entry compiler)

`fc789b2` (R1-C plan approval record) was checked with `git cat-file -t` and returned `commit`.

### Packaged lexicons (provisional v1)

Lexicon files are under `src/litmus/quality/lexicons/`, are package data in `pyproject.toml`, and are marked `-text` in `.gitattributes`. The SHA-256 values are of the raw file bytes:

| File | Version | Entries | SHA-256 |
|---|---|---|---|
| `claim_phrases_to_inspect.txt` | 1 | 14 | `6ef25f0591733bd04d317d29fbdf82bba1dd311dea6b2eb320c45cfd260ee705` |
| `hedges.txt` | 1 | 20 | `d2625f88fa1b9ac4b784590fa3e16128791e35c71ee606f8cfd079123da09805` |
| `stock_phrases.txt` | 1 | 20 | `781b44148b65ac55fa394cc87ab8947e36f13e3ed7d56d3ff8045251c974d637` |

- **Header:** each file says `author: drafted with AI assistance (Claude Code) for the Litmus project; reviewed by Ryan` and `license: OPEN — pending Ryan's decision`.
- **Hedges:** `hedges.txt` has a comment line recording that `may` is omitted.
- **Tests:** a default-suite test checks that each committed lexicon's version, entry count and SHA-256 match this table.

### Implementation choices

- **Duplicates:** two entries are also duplicates if they differ only in apostrophe variants (`'` vs U+2019) or hyphen variants (`-`, U+2010, U+2011). Both would compile to the same pattern, so this is stricter than casefold alone.
- **Strict file format:** the validator also rejects a BOM, carriage returns (LF only), non-UTF-8 bytes, and entries containing control or format characters or `#`.
- **Resource names:** lexicon names are restricted to `[a-z][a-z0-9_]*` before any resource lookup.

### Tooling note: escapes written as literal characters

- While writing C1, the file-writing tool stored `\uXXXX` escapes as the literal characters, including invisible ones (U+200B, U+200D, combining marks, unassigned code points at the block edges).
- All new C1 files were rewritten mechanically so that non-docstring string literals use escapes again. The parsed AST was identical before and after for every file.
- An audit of all tracked `.py` files found one pre-existing literal U+200B: the `zero_width_space` fixture in `scripts/tokenizer_checks.py` (R1-A). It is intentional and behaves correctly. It was left unchanged because it is out of C1 scope.

### Not in C1

- Observers, report/CLI integration and `--quality` are C2.
- No RAID data, calibration, C2PA work or origin-scoring changes.

## 2026-10-30 — R1-C1 closure

- **2026-10-30: R1-C1 closed.** Independent review (Codex) of `1891140`: 387 default tests passed; Ruff passed; a fresh installed-wheel check outside the repository passed resource, hash, loader, matcher, and model-stack isolation checks; repository clean. Ryan approved starting R1-C2.
- These results were reported by the reviewer and by Ryan. They are recorded as reported and were not run by the agent for this entry.
- `1891140` was checked with `git cat-file -t` and returned `commit`.