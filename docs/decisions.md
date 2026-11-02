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

## 2026-10-30 — Checkpoint R1-C2 (text quality observers, `--quality`)

- **Observers:** `src/litmus/quality/observers.py` (`observer_version = "1"`): `stock_phrases`, `hedges`, `repeated_word_3grams`, `claim_phrases_to_inspect`, in that report order. Fields, notes format, the 1,000-span cap and error behavior are in `docs/interfaces.md` ("Text quality observations (R1-C2)").
- **Integration:** `litmus analyze FILE --quality {off,on}`, default `off`. Off constructs and runs nothing; the default-suite tests check that output is byte-identical to the committed golden files. With `on`, origin is computed first, text segments get four observations, image segments keep `quality: []`, and six quality limitations are appended to the report.
- **Scoring hash unaffected:** `report.py`, `cli.py` and `litmus/quality/*` are not in the `scoring_config_hash` source list.

### Implementation choices

- **Claim note:** the plan's two claim notes are one note, `label=phrase to inspect; not evidence that a claim is unsupported`, as worded in the C2 prompt.
- **Errors:** an exception yields `error=<exception class name>` (class name only, no message text). An invalid packaged lexicon yields `lexicon_invalid=<reason>`.
- **Construction before analysis:** with `--quality on`, the CLI constructs the observers (lexicon load and compile) before analysis starts.
- **Limitations on non-text input:** with `on`, the quality limitations are appended to every report, including reports with only image segments.

### Installed-wheel check (agent run)

- Run in `C:\Users\Ryano\AppData\Local\Temp\litmus-c2-7aae6b9c-203e-4968-99c3-235f1b1c8587` (left in place).
- `scripts/verify_wheel_lexicons.py` gained check (f): construct and run all four observers from the installed package on a fixed sample. Expected counts: 2 / 3 / 8 / 2.
- Result: PASS, 0 failures.

### Quality benchmark (agent run)

`scripts/benchmark_quality.py` writes `eval/results/r1c2_quality_benchmark.json`; the console log is `eval/results/logs/r1c2_quality_benchmark.log`.

- **Machine:** Intel Core i7-14650HX, 16,869,634,048 bytes RAM, Windows 11 (10.0.26100), Python 3.13.7. On battery (56%), Balanced power plan.
- **Method:** 1 warmup and 5 timed runs per input. Median total (word index plus four observers) at 200,000 code points:
  - typical prose: 0.2106 s;
  - adversarial high-match: 0.1978 s.
- **Flags:** none against the 5 s target.
- **Caveat:** the typical-prose input repeats one paragraph, so nearly every word 3-gram repeats. Its `repeated_word_3grams` count is not representative of real prose.
- **Not measured:** timing on AC power.

### Not in C2

- No RAID data, calibration, C2PA, UI or origin-scoring changes.
- No optimization.
- Lexicon licensing remains OPEN — pending Ryan's decision.

## 2026-10-30 — R1-C2 corrections

- **Reviewer-reported (not run by the agent for this entry):** Codex reviewed R1-C2 through `01c79e7`. It reported 436 default tests passed, Ruff passed, the real-model origin-byte comparison with quality off and on passed, and the repository was clean.
- **Lexicon initialization isolation:** each lexicon observer now also catches `OSError` and its subclasses (for example `PermissionError`) while loading its lexicon. That observer gets an error record with note `error=<exception class name>`; the other observers, origin evidence and the report are unchanged, and the CLI exits 0.
  - `LexiconError` behavior and messages are unchanged. This includes a missing file at the resource read, which is still reported as `lexicon_invalid=lexicon '<name>' is not packaged`.
  - Other exception types are still not caught. They propagate out of the CLI (traceback, exit 1) before analysis starts, as before.
- **Extended quality benchmark (agent run):** `scripts/benchmark_quality.py --suite extended` was added. Results are appended as a separate run under `additional_runs` in `eval/results/r1c2_quality_benchmark.json`; the original measurements are kept unchanged.
  - Log: `eval/results/logs/r1c2_quality_benchmark_extended_20261030T125949.log`.
  - Cases: 200,000 code points of `"a "` repeated, one 200,000-code-point word, and 200,000 CJK code points with no spaces; ordinary prose at 500 / 2,000 / 10,000 code points.
  - Highest median total: 0.1334 s (`"a "` repeated). Nothing was flagged against the 5 s target.
  - Power: on battery (39%), Balanced plan.
  - Caveat: the prose unit is 704 code points, so the 2,000 and 10,000 inputs repeat it, which inflates their `repeated_word_3grams` counts.

## 2026-10-30 — R1-C2 closure

- **2026-10-30: R1-C2 closed.** Independent review (Codex) accepted corrections through `847ae13`: 440 default tests passed; Ruff passed; lexicon initialization failures isolated correctly; expanded quality benchmark covers the requested 200,000-code-point and natural-length cases, preserves earlier measurements, and records no target exceedances. Both benchmark runs were on battery power; AC-power timing was not measured.
- These results were reported by the reviewer. They are recorded as reported and were not run by the agent for this entry.
- `847ae13` was checked with `git cat-file -t` and returned `commit`.
- **Backend routing:** still UNVERIFIED. The instruction's backend line is the unfilled placeholder `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`, so there is nothing to record verbatim. Nothing is inferred from the agent's self-identification.

## 2026-10-30 — R1-D1 approval and R1-D plan corrections

- **2026-10-30: Ryan approved R1-D1 (feasibility) only; D2/D3 not approved.** `a4e6df1` (plan) was checked with `git cat-file -t` and returned `commit`.
- **Corrections** (full text in `docs/plans/R1-D-PLAN.md` §p; they govern where they differ from earlier sections):
  1. **Context-aware mapping.** Validation codes are mapped by the manifest and assertion they belong to. An `assertion.action.ingredientMismatch` on the active claim affects the active manifest.
  2. **Timestamps.** A timestamp failure need not invalidate the claim signature, and `insideValidity` does not by itself prove a verified signing time; D2 treats them separately. The supporting C2PA specification section is **UNVERIFIED**: no copy is available offline, and network access is not permitted.
  3. **Timeout is a response deadline.** One dedicated worker per process; at most one outstanding C2PA task; `c2pa_worker_busy` while a timed-out task still runs; the worker owns and releases the task's buffers and handles; threads do not accumulate.
  4. **Trust claims.** SDK trust observations are recorded separately from Litmus's policy, which is an explicit, empty, packaged production anchor list.
- **D3 preferences (recorded, not implemented):** a minimal unsigned-metadata summary; `--c2pa` off by default.
- **Certificate fallback: pending.** If local generation fails, the exact failure is reported and that branch stops. No third-party files are added.
- **Backend routing:** still UNVERIFIED. The instruction's backend line is the unfilled placeholder `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`.

## 2026-10-30 — Checkpoint R1-D1 (C2PA feasibility; analysis still disabled)

Production C2PA analysis stays **disabled**. The CLI image report is unchanged: golden bytes, `image_origin_placeholder`, reason `c2pa_analyzer_disabled_in_r0`. There is no mapping, no rule engine and no CLI flag (D2/D3 not approved).

### Production trust list and settings builder

- **Trust list:** `src/litmus/c2pa/trust/production_trust_anchors.pem` is packaged (`pyproject.toml` package-data; `-text`) and loaded via `importlib.resources`.
  - Header: name, version 1, date 2026-10-30, license "OPEN — pending Ryan's decision", policy, format.
  - Zero certificates. This is Litmus's policy (§p Correction 4); it is not a claim about the SDK.
- **Settings builder:** `src/litmus/c2pa/settings.py`.
  - `production_config()` returns the A1.2 keys plus `verify.verify_trust = true`. It refuses a non-empty production list.
  - `test_anchor_config(pems)` is the only path that adds `trust.trust_anchors`.
  - Configs are applied with `c2pa.Settings.from_dict` (`c2pa/c2pa.py`: `from_dict` → `from_json` → `update` → native `c2pa_settings_update_from_string`) and `c2pa.Context(settings=...)`.
  - The builder's contents are **not evidence of effect** (unknown keys are silently accepted, R0).
- **SDK observation: `Settings.set` vs `from_dict` for trust.** Same `trusted_signer` fixture, same test root PEM:
  - `Settings.set("trust.trust_anchors", <json string>)` and `Settings.set("trust.user_anchors", ...)` left `signingCredential.untrusted` / `Valid`.
  - `Settings.from_dict({"trust": {"trust_anchors": pem}})` gave `signingCredential.trusted` ("signing certificate trusted, found in [system_anchors] trust anchors") / `Trusted`.
  - `from_dict` with `user_anchors` gave "found in [user_anchors] trust anchors".
  - Test: `test_settings_set_trust_anchors_had_no_observed_effect`. The cause was not investigated. The builder uses `from_dict` for every key, so the offline evidence below was re-established through that route.

### Certificates and fixtures

- **Certificate generation: succeeded.** The library accepted locally generated certificates both for signing and for validation; nothing was rejected.
  - Generated with `cryptography`: ECDSA P-256, ES256.
  - Test root → intermediate → signer, plus a separate untrusted root → signer.
  - Validity 2026-01-01 to 2046-01-01 (stated in `tests/fixtures/c2pa/pki/README.txt` and `manifest.json`).
  - End-entity profile: BasicConstraints CA=false (critical), KeyUsage digitalSignature (critical), EKU emailProtection, SKI, AKI.
  - No TSA (`ta_url=None`). No third-party files.
- **Fixtures:** produced by `scripts/generate_c2pa_fixtures.py` into `tests/fixtures/c2pa/`, with SHA-256 values and generator parameters in `manifest.json`.
  - The remote-reference fixture points at `http://127.0.0.1:47811/manifest.c2pa`.
  - Signing used the offline settings plus `builder.thumbnail.enabled = false`. That setting's effect was observed as smaller outputs (for example, `trusted_signer.webp` went from 610,198 to 4,158 bytes).

### Captured library output (`eval/results/r1d1_library_outputs/`)

`scripts/capture_c2pa_outputs.py` captured 24 reads: 12 fixtures × 2 configurations. Log: `eval/results/logs/r1d1_capture.log`. Observations:

- **No manifest** (JPEG, PNG, WebP): `_C2paManifestNotFound`, "ManifestNotFound: no JUMBF data found".
- **Remote reference:** a generic `C2paError` (not the `RemoteManifest` subclass), message "Remote: must fetch remote manifests from url http://127.0.0.1:47811/manifest.c2pa". Plan §e: D2 needs an approved detection rule.
- **Valid signed fixtures, production config:** state `Valid`.
  - success: `assertion.dataHash.match`, `assertion.hashedURI.match`, `claimSignature.insideValidity`, `claimSignature.validated`;
  - informational: `signingCredential.ocsp.skipped`;
  - failure: `signingCredential.untrusted`.
- **Same fixtures with the test anchor:** state `Trusted`; `signingCredential.trusted` appears in success, and nothing is in failure. This holds for the trusted, active-AI and ingredient fixtures in every format.
- **Tampered:** state `Invalid`; failure includes `assertion.dataHash.mismatch`, and the signature codes remain in success.
- **Ingredient-only:** two manifests (active plus the ingredient's).
  - The ingredient's `relationship` is `componentOf` and its title is `active_ai_declared.jpg`.
  - The ingredient's own manifest shows `trainedAlgorithmicMedia`.
  - `ingredientDeltas[0]` (keyed by the ingredient assertion URI) lists `ingredient.manifest.validated`, plus `signingCredential.trusted` with the test anchor.
- **No `timeStamp.*` codes in any output** (no TSA). Correction 2 states therefore have no real fixture yet.

### Offline evidence (Addendum B4)

- **Zero attempted connections observed (with passing control)**, for `remote_reference.jpg` with the settings applied by `production_config()` / `from_dict`:
  - Trap: **0** connections.
  - Positive control (`verify.remote_manifest_fetch = true`, `core.allowed_network_hosts = ["127.0.0.1:47811"]`): **1** connection, `GET /manifest.c2pa`.
  - Tests: `test_remote_reference_zero_connections_with_production_settings`, `test_remote_reference_positive_control_reaches_trap`.
  - Valid for this fixture and configuration only.
- **Passes under network isolation:** not run. Docker isolation was not run and nothing was pulled.

### Test-anchor effect (SDK observations, not policy claims)

- `trusted_signer.jpg`:
  - with the test anchor: `signingCredential.trusted`, `Trusted`;
  - production settings: `signingCredential.untrusted`, `Valid`.
- `untrusted_signer.jpg` with the test anchor: `signingCredential.untrusted`, `Valid`.
- Nothing is concluded about built-in SDK anchors beyond these observations.

### Non-ASCII audit exception (pre-existing)

- `tests/conftest.py:11` has a U+00A7 (`§`) in the comment `# SPEC §7: ...`, from `18c7cbc` (R0). It is a comment, not a string literal, and is unchanged. It is listed because `conftest.py` changed in R1-D1 (trap port parameter).

## 2026-10-30 — R1-D1 closure

- **2026-10-30: R1-D1 closed.** Independent review (Codex) through `64ab969`: 463 default tests and Ruff passed; fixture hashes and 24 captured reads matched; remote-reference trap and positive control passed; test-anchor effects confirmed. Production C2PA remains disabled. Ryan approved R1-D2 only.
- These results were reported by the reviewer and by Ryan. They are recorded as reported and were not run by the agent for this entry.
- `64ab969` was checked with `git cat-file -t` and returned `commit`.
- **Scoped observation (no cause stated):**
  - **Setup:** c2pa-python 0.38.0, SDK 0.91.0 (`c2pa.sdk_version()`).
  - **Input:** `tests/fixtures/c2pa/trusted_signer.jpg`, read with `Reader("image/jpeg", BytesIO(bytes), context=Context(settings=...))` and the A1.2 offline settings.
  - **Observed:**
    - `Settings.set("trust.trust_anchors", json.dumps(<test_root_ca.pem text>))` and `Settings.set("trust.user_anchors", ...)` left the result at `validation_state = "Valid"` with `signingCredential.untrusted`.
    - `Settings.from_dict({"trust": {"trust_anchors": <same PEM>}})` gave `"Trusted"` with `signingCredential.trusted`.
  - **Scope:** this was observed only for these inputs and this SDK version (test `test_settings_set_trust_anchors_had_no_observed_effect`).
  - **Consequence:** `Settings.from_dict` remains the configuration route.
- **Backend routing:** still UNVERIFIED. The instruction's backend line is the unfilled placeholder `[PASTE THE /status PROVIDER AND MODEL LINES HERE]`.

## 2026-10-30 — R1-D2 continuation and implementation (pending independent review)

### Scope and starting state

- Ryan authorized D2 completion only, committing the implementation and actual
  evidence, then stopping for independent review. D1 was already accepted.
- Starting HEAD matched `e88a3e5`. There were no tracked modifications. The
  five D2 modules, constructed-output generator and 13 constructed JSON files
  were untracked partial work; they were inspected and retained, with fixes.
  No unrelated changes were stashed, removed or overwritten.
- No repository `AGENTS.md` was found. Work continued in the requested
  checkout using its existing `.venv`; no replacement checkout, dependencies
  or model downloads were created.

### D2 implementation

- Internal `read_store` -> `map_store` -> ordered rules pipeline, isolated from
  the CLI and reports. All ten rule results/labels and precedence are tested.
- Context-aware attribution uses manifest labels and assertion URLs, including
  active `assertion.action.ingredientMismatch`, ingredient-only failures,
  relative stored ingredient URLs and unknown/missing URLs. Current trust
  deltas supersede stored ingredient trust. Unreferenced manifests cannot
  trigger rule 9. Raw status entries and unmapped/unattributed entries remain
  available in normalized diagnostics.
- Strict positive evidence is required in success lists. Unknown codes force
  integrity/signature incomplete unless already invalid. Overall SDK state
  does not determine those fields. Exact action labels and IPTC URI matches
  determine declarations; other source types are recorded without declaring.
- Production trust always remains `unknown`, even if SDK diagnostic codes say
  trusted. `TestOnlyPolicy` exists only in tests and must be explicitly passed
  alongside explicit test-anchor settings to exercise trusted outcomes.
- Timestamp state is independent of claim signature. No TSA exists in these
  fixtures. Timestamp successes, ignored failures and signing-time basis
  behavior are constructed policy tests, not real timestamp validation.
  The inherited C2PA 2.5 section 14.8 reference remains UNVERIFIED; no online
  specification was consulted and no supporting section is claimed verified.
- One lazy worker, one outstanding task, no queue or replacement on timeout.
  Deadline returns `c2pa_timeout`; new work while busy returns
  `c2pa_worker_busy`. Native work continues. The worker closes resources and
  releases input references, abandoned outputs and exception traceback frames
  before publishing idle. Tests cover recovery, 30 immediate busy requests,
  concurrent callers, stable worker thread identity/count and cleanup on
  success/error paths after both completed and timed-out requests.
- The three reported Ruff errors were reproduced: E501 in `mapping.py`,
  `reader.py` and `scripts/make_c2pa_constructed.py`. All were fixed without
  weakening lint configuration.
- Regression tests initially exposed wrong-list positive evidence, overly
  broad actions labels, incomplete unknown-code handling, a KeyError on
  unattributable stored ingredient statuses, missing settings-rejection
  reasons, orphan declaration handling and unrecorded near-miss URIs.
  These were corrected. An initial test also used the wrong capture filename
  (`test_anchor` instead of the existing `test_anchors`); the test was fixed.

### Actual verification (this agent, Windows, existing venv)

- `.venv/Scripts/python.exe -m pytest tests/test_c2pa_d2.py tests/test_c2pa_d2_worker.py -q --tb=short`:
  **165 passed in 1.63 s**, exit 0.
- Inside `C:\Users\Ryano\Projects\litmus`:
  `.venv/Scripts/python.exe -m pytest -q`:
  **628 passed, 20 deselected in 9.67 s**, exit 0.
- Outside, cwd `C:\Users\Ryano`:
  `C:/Users/Ryano/Projects/litmus/.venv/Scripts/python.exe -m pytest C:/Users/Ryano/Projects/litmus/tests -q`:
  **628 passed, 20 deselected in 8.65 s**, exit 0.
- `.venv/Scripts/python.exe -m ruff check src tests scripts`:
  **All checks passed!**, exit 0.
- `.venv/Scripts/python.exe -m pip check`:
  **No broken requirements found.**, exit 0.
- `git diff --check`: exit 0. Git reports ordinary LF-to-CRLF notices for
  text files; no whitespace errors were reported.
- The full suite includes D1 fixture hashes, all captured SDK reads, package
  trust/settings checks, image golden byte equality (LF-normalized), and
  CLI C2PA import isolation. The production CLI/report/golden files were not
  modified. C2PA analysis remains disabled.
- Early sandbox test runs emitted pytest-cache access warnings. Final test
  runs were approved outside the sandbox and completed without those warnings.

### Evidence and limitations

- The mapping has **45 codes**. All have constructed-store tests committed in
  `constructed/mapping_rows.json`; **9 codes** also occur in real D1 captures.
  The other **36** have no real SDK emission demonstrated; the complete table
  and observation split are in `docs/interfaces.md`. No mapping row lacks
  test coverage. Synthetic injection never establishes SDK emission.
- Both remote-reference variants (committed Builder JPEG and existing XMP
  fixture construction) passed through the D2 pipeline with production
  settings: rule 4, **0 trap connections** each. Each paired positive control
  recorded **1 connection**, `GET /manifest.c2pa`; the trap deliberately
  returned 404, producing rule 2. This is zero attempted connections observed
  with passing controls for these fixtures/settings/destination only.
- The generic-error message adapter is pinned to c2pa-python 0.38.0 / SDK
  0.91.0 and exact prefix, with fetch explicitly disabled. Other versions,
  prefixes or enabled-fetch configurations fail closed. It remains fragile.
- Not run: the 20 slow/model-dependent tests, real TSA/timestamp validation,
  real 120-second native hang, Docker/network isolation, Linux SDK runs,
  wheel rebuild, models/calibration/RAID, D3 integration or UI. No new
  dependencies, external fixtures, network downloads or destructive cleanup.
- Daemon process exit during an unfinished native call cannot promise native
  resource cleanup. Constructor-internal cleanup remains owned by the SDK;
  returned resources are explicitly closed on the worker.
- This is an implementation submission, not independent-review acceptance.

## 2026-10-30 — R1-D2 closure and R1-D3 approval

- **D2 closed, reviewer-reported.** Ryan reported Codex's independent review
  of `0c6fa08`: 628 default tests, Ruff and pip check passed; both remote
  trap/control variants and bounded-worker tests passed; the repository was
  clean. Those reviewer results are recorded as supplied, not builder-run.
- Ryan approved `docs/plans/R1-D3-BUILD-PROMPT.md` and authorized D3 only,
  preserving work/evidence, committing implementation plus actual checks,
  then stopping for independent review. The previously untracked complete
  prompt is retained, marked approved, with Ryan's wheel-check clarification.
- **Wheel clarification:** existing pinned runtime dependencies must remain
  available without downloads/new dependencies, while Litmus must import
  from a freshly installed wheel rather than the editable checkout.
- Starting HEAD matched `0c6fa08edeb856633e86a65667461c73b1708bca`. The only
  untracked file was the saved D3 prompt; no tracked changes existed. No
  repository AGENTS.md was found. Work continued in the requested checkout
  with its existing .venv. No existing work/evidence was removed or stashed.
- **Citation attribution correction:** the C2PA 2.5 section 14.8, “Validate
  the time stamp,” citation was supplied by the reviewer:
  https://spec.c2pa.org/specifications/specifications/2.5/specs/C2PA_Specification.html#_validate_the_time_stamp.
  The builder did not independently fetch or verify the specification text.
  Earlier builder statements about an inherited/Ryan citation are preserved
  as historical entries and superseded here. Current documentation and
  constructed-fixture descriptions now use reviewer attribution. Constructed
  timestamp tests remain policy evidence only; no real TSA validation follows.

## 2026-10-30 — R1-D3 implementation (pending independent review)

### Delivered scope

- `--c2pa {off,on}`, default off. Only accepted JPEG/PNG/WebP image segments
  invoke the lazy production adapter using ingested bytes/MIME. Text-only and
  rejected inputs do not initialize the SDK/worker. Omitted/off golden bytes
  remain unchanged. Text origin/quality and scoring source/hash behavior are
  unchanged; model-free stub comparisons verify report preservation.
- C2PA OriginEvidence version 1 contains active/referenced ingredient records,
  independent validation/timestamp/trust/declaration fields, trust-list
  identity/hash/count, library versions, requested settings, raw attributed
  statuses, unknown/unattributed diagnostics, rule/reasons and limitations.
  Scores/calibration are null. Unknown presence/validation/timing values are
  null/empty with notes; no successful read or settings application is invented.
- Reader/pipeline additions expose diagnostics only: settings application and
  read/response durations. The D2 rule/mapping/worker semantics are preserved.
  The worker implementation and the 45-code mapping table were not changed.
- The explicit activation constant records reviewed offline evidence through
  0c6fa08; runtime does not probe the network or execute tests. Missing evidence,
  invalid trust resources, SDK import failure or version drift refuse activation
  (CLI exit 1, stderr, no report/output-file write). Post-initialization analyzer
  errors produce rule-2 evidence, CLI exit 0 when the report is emitted, without
  falling back to a disabled placeholder. Argument errors exit 2.
- A minimal unsigned-metadata summary reports EXIF tag count and four truncated
  fields, plus Pillow-exposed XMP presence/length. Each component failure is
  isolated. It is labeled unverifiable/editable/not evidence and never changes
  result/reasons or signed validation/declaration data. EXIF DateTime is not
  verified signing time. Metadata is read from memory, not the input path.
- Report/evidence round-trip, CLI/error behavior, fresh-process import isolation,
  short deadline/busy/recovery behavior, both enabled remote trap/control pairs,
  default byte identity and metadata invariance/isolation are covered by 32 new
  model-free integration tests. The existing quality-test stub was adapted to
  forward the added keyword-only report option; observer behavior is unchanged.
- README status, interfaces, approved build prompt and D-plan were reconciled
  with reviewed D1/D2 evidence. The nine-real/36-constructed mapping distinction,
  explicit empty trust policy and absence of real timestamp validation remain.
  Only citation-description metadata changed in the constructed timestamp JSON;
  underlying stores and all earlier D1/D2 captured/verification evidence remain.

### Fresh builder-run verification

- Inside `C:\Users\Ryano\Projects\litmus`:
  `.venv/Scripts/python.exe -m pytest -q`:
  **660 passed, 20 deselected in 11.17 s**, exit 0.
- Outside, cwd `C:\Users\Ryano`:
  `C:/Users/Ryano/Projects/litmus/.venv/Scripts/python.exe -m pytest C:/Users/Ryano/Projects/litmus/tests -q`:
  **660 passed, 20 deselected in 11.45 s**, exit 0.
- `.venv/Scripts/python.exe -m ruff check src tests scripts`:
  **All checks passed!**, exit 0.
- `.venv/Scripts/python.exe -m pip check`:
  **No broken requirements found.**, exit 0.
- `.venv/Scripts/python.exe scripts/audit_c2pa_d3.py --output eval/results/r1d3_non_ascii_audit.json`:
  **PASS: 13 changed/new Python files, 2 comment/docstring findings, 0
  code/runtime-literal violations**, exit 0. This is a scoped source audit,
  not a claim that the entire repository lacks intentional Unicode fixtures.
- `.venv/Scripts/python.exe scripts/verify_wheel_c2pa.py --output eval/results/r1d3_wheel_check.json`:
  **PASS**, exit 0. Scratch directory:
  `C:\Users\Ryano\AppData\Local\Temp\litmus-d3-wheel-vr_xa0e9` (retained).
  Built offline with --no-index --no-deps --no-build-isolation; installed only
  Litmus into a fresh target with --no-index --no-deps. The child ran -I from
  outside the repository using the existing venv runtime dependencies. Every
  loaded Litmus module resolved inside the wheel target. Pillow 13.0.0,
  c2pa-python 0.38.0 and SDK 0.91.0 came from the existing venv. Resource hash
  and empty trust matched; only the empty production PEM was packaged, with
  no test keys/anchors. Enabled JPEG/PNG/WebP, default golden and no-model-import
  checks passed. pip freeze --all before/after was identical.
- `git diff --check`: exit 0 (ordinary LF/CRLF notices, no whitespace errors).
- Real report snapshots for eight committed fixtures are in
  `eval/results/r1d3_image_reports.json`; all mapped production trust is unknown
  and every real timestamp state is absent. Timing values are observations,
  not a benchmark or calibration. `r1d3_verification.json` indexes results/files.

### Observations, limitations and not run

- Both enabled Builder and XMP variants returned rule 4 with zero trap
  connections; each paired control recorded one GET /manifest.c2pa and the
  trap's deliberate 404, yielding rule 2. This is zero attempted connections
  observed with passing controls for these fixtures/settings/destination only.
- The first full suite exposed four existing quality-test stub signature
  mismatches; these were fixed by forwarding the new keyword. The first D3
  tests failed before implementation as expected. Early sandbox runs had
  pytest cache/temp access failures; approved final runs did not.
- One standalone report capture inside the sandbox failed initialization with
  `subprocess.Popen blocked during analysis`. Fresh-process reproduction and
  capture outside the sandbox passed. No broader cause is asserted and no
  network/subprocess guard was weakened to make the capture succeed.
- Not run: 20 slow/model-dependent tests, real-model on/off comparison, actual
  TSA/timestamp validation, a real 120-second native hang, Docker/network
  isolation or Linux SDK execution. No production anchors, calibration, RAID,
  image detector, UI, new dependencies or external fixture acquisition.
- Timeout remains response waiting, not cancellation. The worker owns native
  resources until completion; daemon process exit while work is running cannot
  guarantee cleanup. Constructor-internal failed-handle cleanup belongs to the
  SDK. Version/prefix-dependent remote classification remains fragile.
- D3 is submitted for independent review, not marked independently accepted.

## 2026-10-30 — R1-D3 and R1-D closure; R1-E planning only

- **D3 and R1-D closed, reviewer-reported.** Ryan supplied Codex's independent
  review of `d7ed91f`: 660 default tests, Ruff, pip check, whitespace checks and
  a fresh installed-wheel check passed. The reviewer recommended closing D3
  and R1-D; Ryan instructed recording closure. These are reviewer-reported
  results, not checks rerun by the builder for this documentation entry.
- `d7ed91f` was checked with `git cat-file -t` and returned `commit`. Planning
  began at `d7ed91fc949087cee271ac51dcc058bc2a115f48` with a clean working tree.
  No repository AGENTS.md was found. Existing implementation and D1–D3 evidence
  records are preserved. C2PA remains opt-in, default off.
- Ryan authorized an R1-E preparation plan and acquisition approval request
  **for independent review only**. No dataset payload download, pipeline
  implementation, selection, scoring, calibration, test evaluation or UI work
  is authorized by this instruction. N_target=1,000 source groups remains the
  existing approval; it is not acquisition permission.
- Saved proposed documents: `docs/plans/R1-E-PLAN.md` and
  `docs/plans/R1-E-ACQUISITION-APPROVAL.md`. Seed 20261030, acquisition budgets,
  pin/identity verification, attack multiplicity tie policy and implementation
  phases are proposals awaiting approval. The plan uses independent CA1 tags,
  source-unique cell quotas, grouped dev/test, exact raw/window deduplication,
  ordered pair cleanup and a reproducible count/exclusion manifest. It forbids
  scoring in E and preserves the ≥200 eligible dev-human gate for future 5%
  calibration; 1% calibration remains disabled.
- **Metadata/documentation research only:** inspected authors' public RAID
  repository, dataset card, revision/file metadata and loader/license source.
  No CSV payload was fetched. Proposed dataset pin is
  `liamdugan/raid@865cac74188466cb0c3b7574a10204007b57a459`, train.csv only.
  The publisher advertises 11,779,491,051 bytes and SHA-256
  `52f04ceebc126064e68fbd22d8b736964065745464f4bfd52e488150b49f84e4`.
  The immutable file-addition commit and current file page supply those values;
  the selected revision's tree is verified, but its exact pointer/API could
  not be retrieved by the browser. Future approved acquisition must confirm
  the revision-specific pointer before transferring the payload. No local
  payload integrity or raw schema/population verification is claimed.
- The official card declares MIT; underlying source-corpus redistribution terms
  were not fully audited. The request is local evaluation only, no raw-text
  publication or project-license decision. Official mutable direct CSV URLs
  are documented but not an automatic fallback for the pinned route.
- **Pre-E gap:** CA1 key implementation/tests are absent from the checkout.
  The plan makes their verification a prerequisite before acquisition/selection;
  no code was written to fill that gap in this planning-only task.
- Current local disk observation: 419,241,680,896 bytes free on C:. Proposed
  acquisition requires rechecking ≥30 GB free, limits cumulative payload transfer
  to 13 GB and incremental task artifacts to 25 GB. Costs/times in the plan
  are estimates, not measured acquisition or preparation results.
- Runtime tests, installed-wheel checks and scorer/model calls were not run
  for this documentation-only task. Source URLs and explicit unknowns are
  recorded in the plan. No new dependencies or data directories were created.

## 2026-10-31 — R1-E approval and execution scope

- Ryan approved `docs/plans/R1-E-PLAN.md` and the bounded acquisition request,
  authorizing E0–E6 data preparation only. Explicitly approved: seed 20261030,
  N_target=1,000 source groups, proposed attack tie-break/hash encodings,
  metadata-only selection and no refill after exclusions.
- Approved file: train.csv only, revision
  `865cac74188466cb0c3b7574a10204007b57a459`, 11,779,491,051 bytes, SHA-256
  `52f04ceebc126064e68fbd22d8b736964065745464f4bfd52e488150b49f84e4`.
  Limits: 13,000,000,000 cumulative payload bytes; at least 30 GB free before
  acquisition; at most 25 GB incremental task artifacts. Local evaluation only,
  no raw-text redistribution or Git inclusion. No paid services/dependencies.
- **Reviewer-reported:** Ryan stated Codex independently confirmed the pinned
  revision's API metadata matches the approved size/hash. This supersedes the
  planning uncertainty; it is not a builder-run preflight. The builder must
  repeat identity preflight before transfer and verify downloaded length/hash.
- Starting HEAD remains `d7ed91f`. The pending README, decisions and D-plan
  edits plus the two untracked R1-E planning documents are preserved. No
  repository AGENTS.md was found. CA1 must be implemented and verified first;
  raw-data ignore rules must precede acquisition. Final outcomes are recorded
  separately after execution, without treating prior recaps as completion.
- Stop on approved identity, schema, budget or reproducibility failures.
  No scoring, calibration, test evaluation, UI or scope expansion is authorized.

## 2026-10-31 — R1-E implementation and measured preparation results

- E0 was verified before acquisition: nine CA1 tests passed; combined key and
  initial acquisition tests passed (12). Fixed goldens, literal-byte oracle,
  Unicode/type/boundary/order tests use independent select/split/row tags.
  Synthetic selection from 100,000 IDs produced 303/1,000 dev assignments,
  within the predeclared [240,360] tolerance; seed 20261030 was not changed.
  `eval/results/r1e_ca1.json` preserves this prerequisite evidence.
- `/data/` was ignored before transfer. The builder repeated the approved
  revision-specific API preflight, then accepted one train.csv after matching
  length 11,779,491,051 and SHA-256
  `52f04ceebc126064e68fbd22d8b736964065745464f4bfd52e488150b49f84e4`.
  This is builder-observed evidence in preflight/acquisition receipts, distinct
  from the earlier reviewer-reported metadata confirmation. No mutable fallback,
  publisher test/extra artifact, automatic retry or duplicate raw copy was used.
- Measured acquisition: 1,828.064 s, 426,871,160,832 bytes free before transfer,
  11,779,495,917 received HTTP payload bytes including metadata, and conservative
  charged usage 11,781,588,203 bytes against the 13,000,000,000 cap. Charging is
  durable before reads and never refunds unused reservations, so it bounds
  potentially received payload across interruptions for Budget.read calls only;
  the redirect-body gap discovered below limits the cumulative-budget claim.
  The only redirect host
  observed was us.aws.cdn.hf.co. Signed redirect query strings were not saved.
- Full strict UTF-8 CSV scan: 5,615,820 unique row IDs, EOF reached, no file BOM.
  Eleven attack methods plus clean `none` were observed, each with 467,985 rows.
  All eight allowed domains and eleven generator labels were present, plus
  `human`; exact settings/label counts are in primary/counts.json. The 13,371
  clean human rows each have empty decoding/penalty settings and matching
  id/source_id/adv_source_id. No critical schema ambiguity was encountered.
- Metadata selection found 13,371 eligible sources and 88 cells. Every quota
  filled: first 32 sorted cells at 12, remaining 56 at 11; no reallocation or
  shortfall. Frozen candidates: 1,000 source groups/5,000 rows, 306 dev and
  694 test groups. All three requested attacks were available for each chosen
  parent; no multiplicity tie or parent mismatch occurred for those attachments.
  Selection never inspected generation/title/prompt content. The CSV parser
  necessarily decoded transport text before discarding unselected content.
- Eligibility excluded 72 short texts: 5 human, 20 machine, 41 paraphrase,
  3 homoglyph and 3 zero_width_space. Raw/window collision channels identified
  the same two human rows in different source groups; both were removed.
  Counts record two channel records, not four distinct row participants.
  Ordered clean-pair cleanup removed another 81 rows. Total exclusions: 155;
  group attrition: 27. No refill, split movement or seed/target change occurred.
- Retained: 973 groups/4,845 rows, with 973 clean human/machine pairs, 973
  homoglyph, 953 paraphrase and 973 zero_width_space rows. Dev: 298 groups and
  1,484 rows; test: 675 groups and 3,361 rows. No cross-group raw/window equality
  remains. Within-group attack no-ops were retained: zero raw, one window;
  the all-role within-group equality audit found that same window equality.
  Zero-filled slice/cell tables, exclusions, collisions and no-ops are retained.
- The existing pinned observer tokenizer was used locally without weights,
  scoring imports, torch/TensorFlow, CUDA or network. Real run guards and the
  exact tokenizer-only test provide observations; they are not an OS sandbox.
  Local blobs preserve exact UTF-8 generation bytes, including embedded newlines
  and attack characters. Raw CSV, metadata indexes and blobs remain ignored.
- 298 eligible development human texts satisfy only the numerical ≥200
  prerequisite for possible future 5% calibration. No scores, thresholds,
  calibration or test evaluation were produced. The 1% calibration remains
  disabled. R1-F/R1-G require separate authorization after independent review.
- Remaining limits: one pinned train artifact and one approved seed; domain
  membership is an English-oriented proxy, not row-language verification.
  Underlying source-corpus rights were not exhaustively audited; MIT is the
  publisher's dataset declaration and local use remains the approved scope.
  No raw-text redistribution, project-license decision or dependency change.
  Production analyzers/default reports and prior D1–D3 evidence are preserved.
- **STOP — full cumulative acquisition budget is not proven.** Final source
  inspection found that urllib's HTTPRedirectHandler.http_error_302 invokes
  fp.read() before following a redirect. ArtifactRedirect delegates to that
  implementation, so redirect bodies bypass Budget.read. A synthetic adapter
  probe consumed 23 body bytes with unchanged durable counters and no network;
  see `eval/results/r1e_redirect_budget_audit.json`. The actual redirect-body
  length was not captured during acquisition. Counted API/artifact reads remain
  below 13 GB, and no actual overrun is established, but they do not prove the
  approved cumulative limit. Earlier broad counter descriptions are narrowed
  by this finding. R1-E is stopped and not complete/accepted despite valid raw
  identity and prepared outputs. No reacquisition, source patch or new data
  preparation was performed after the finding. The in-flight read-only verifier
  may finish; all work/evidence is preserved for independent review. A later
  fix alone cannot retrospectively measure the missing redirect-body bytes.
- The in-flight raw-backed verifier completed exit 0 / PASS in 332.295 s:
  raw length/SHA-256, source/tokenizer/index identities, reconstructed selection,
  5,615,820 rows to EOF, all 5,000 candidate text assessments, 4,845 retained
  blob comparisons, cleanup and parent/split/count invariants passed. All seven
  primary/repeat scientific files are byte-identical; manifest payload SHA-256
  is `8f0a36e95e9745e27bd444b94fe96381c5c0cd98744b2abd52bd2a6ce579c5d9`.
  Both preparation runs and verifier reported zero connection, weight-access
  or forbidden-import attempts. Primary/repeat elapsed 447.237/634.764 s and
  CPU 351.969/521.656 s; peak working sets 491,020,288/492,400,640 bytes.
  Raw plus both local runs and manifests totaled 14,213,226,786 bytes; including
  the 64 MiB small-artifact reserve, 14,280,335,650 bytes (<25 GB). This is a
  storage observation, not a cure for the separate transfer-accounting gap.
- Checks on frozen source: inside defaults 700 passed/21 deselected (14.95 s);
  outside-repository defaults 700 passed/21 deselected (15.47 s); exact local
  tokenizer-only slow test 1 passed (2.21 s); synthetic E slice 40 passed (1.60 s).
  Ruff passed, pip check reported no broken requirements, scoped source audit
  passed (20 Python files, zero findings/violations), and whitespace checks
  passed. Exact commands and limitations are in eval/results/r1e_verification.json.
  These green checks did not cover redirect-body budget accounting; the focused
  audit above exposes that gap. No full model/GPU slow suite, real-data scoring,
  calibration, test evaluation or fresh installed-wheel check was run for E.
- Work is committed for independent review with **R1-E STOPPED, not complete or
  closed**. Existing D1–D3 closure/evidence and pending planning documentation
  are preserved. No source patch or new data operation followed the finding.

## R1-E follow-up — accepted historical uncertainty and offline budget correction

- **Ryan's narrow exception:** Ryan accepted the specific historical uncertainty
  recorded in `eval/results/r1e_redirect_budget_audit.json`. This does **not**
  establish that the original transfer stayed below 13,000,000,000 payload bytes
  and must never be treated as proof of compliance. The original transfer's
  redirect-body count remains unknown; no actual overrun has been established.
  Original counters, receipts, scientific manifests and historical source hashes
  remain unchanged. Keep the existing verified dataset and prepared outputs.
- Authorized follow-up: correct redirect/error response accounting, add offline
  regressions, explicitly reconcile historical versus corrected verifier sources,
  commit evidence, then stop for independent review. No reacquisition, further
  network requests, real-data reselection, scoring, calibration, test evaluation,
  new dependencies or additional scope. R1-E remains pending that review.
- **Reviewer-reported, not rerun as a full default suite here:** Ryan stated
  Codex independently confirmed 700 default tests, Ruff and pip check pass,
  the raw approved length/hash, manifest invariants, repeat-file equality and
  retained text-blob hashes. This attribution does not rehabilitate the original
  transfer accounting. The builder's new checks are reported separately below.
- Baseline at follow-up: clean master at
  `b2d24daba14b80a0cc25c524045e7f713a0363b9`. No AGENTS.md was found. Root cause:
  urllib's redirect handler drained live bodies outside Budget.read; default
  HTTPError could also expose a live response body. Code change is necessary at
  those response handlers; merely changing final-response reads cannot close
  either path. The original 23-byte offline probe remains historical evidence.
- Correction: redirect statuses 301/302/303/307/308 and default HTTP errors share
  bounded 64 KiB draining through the same durable Budget used by API/artifact
  reads. Every real response closes even if storage/transfer budget or read fails.
  Before redirect following, urllib receives an empty surrogate, never the live
  drained stream. Errors expose status-only PrepError. No retry or refund path
  was added. Unused/EOF reservations remain conservatively charged; a budget
  exhaustion stops before following another URL or consuming more body bytes.
- Offline regressions run the real urllib opener/error/redirect handler chain
  with in-memory HTTPS response fixtures and a failing socket-connect guard.
  They cover all redirect aliases, seven error statuses, chained redirects then
  an error, prior payload reducing remaining allowance, budget exhaustion,
  interrupted reads, durable reopening, closure and malformed/disallowed redirects.
  Initial prerequisite tests failed before implementation; corrected paths pass.
  No actual HTTP request or connection was made by these tests.
- Historical verifier handling: unchanged default behavior rejects differing
  preparation source hashes. The explicit reconciliation record binds the exact
  original manifest digest and all 17 historical/current source hashes. Only
  acquisition.py, verification.py and scripts/verify_raid_manifest.py may differ;
  the source-path set must remain identical. Even a matching reconciliation file
  cannot authorize selection/eligibility/cleanup changes. New receipts label
  historical generation separately from current verification and hash the record.
  The CLI requires a new --output with reconciliation and refuses any existing
  output path, preserving the original verification receipt.
- No original scientific identity or selection was regenerated. The reconciliation
  file and follow-up receipts live separately under `eval/results/r1e_budget_fix_*`.
  Synthetic tests cover explicit opt-in success, default rejection, stale/current
  source hashes, wrong historical manifest/source maps, unauthorized changes,
  changed path sets and protected receipt paths. These tests do not relax the
  requirement for independent review of the correction or close R1-E.
- Builder follow-up verification: RAID model-free slice inside the repository
  **68 passed, 1 deselected in 6.62 s**; outside **68 passed, 1 deselected in
  5.72 s**. The first outside run hit sandbox-denied pytest temp-directory setup
  (26 passed, 42 setup errors, 1 deselected); the permitted rerun passed without
  source changes. Ruff passed; pip check found no broken requirements; scoped
  Unicode audit passed (5 Python files, zero findings/violations); whitespace
  checks passed. Exact commands/results are in the separate follow-up evidence.
- Read-only existing-data/source audit passed: raw approved size/SHA-256,
  manifest invariants, all seven primary/repeat scientific file bytes, and
  4,845 retained blob hashes in **each** run. All 26 originally tracked R1-E
  evidence files remained byte-identical to b2d24da, including historical
  receipts, manifests, source maps and the original failure audit. Default
  source mismatch was rejected and explicit reconciliation passed for both
  manifests. Audit guards recorded zero connections, weight accesses and
  forbidden imports. See `r1e_budget_fix_source_verification.json`.
- No full default suite was rerun for this correction: it includes loopback
  network controls, excluded under the no-further-network instruction. No full
  raw-backed verifier/selection reconstruction, real selection/tokenization,
  model/GPU tests, installed-wheel check, scoring, calibration or test evaluation
  was rerun. Synthetic full-verifier integration and actual source-version/
  preservation checks cover the changed seam. The historical transfer cap remains
  **unproven**, and R1-E remains **pending independent review** after this commit.

## 2026-11-01 — R1-E closure and R1-F planning only

- **R1-E CLOSED, reviewer-reported.** Ryan supplied Codex's independent review
  of correction commit `d50b7e0`: 68 offline RAID tests, Ruff, pip check and
  whitespace checks passed. All 26 historical evidence files are preserved;
  explicit source reconciliation validates both runs, and primary/repeat
  scientific files match. These are reviewer-reported results, not runtime
  checks rerun by the builder during this documentation task.
- Closure retains Ryan's existing **narrow historical transfer-accounting
  exception** from r1e_redirect_budget_audit.json. Historical cumulative transfer
  compliance remains **unproven**. Acceptance of uncertainty must never be
  recorded as proof the original transfer stayed below 13 GB. Original receipts,
  scientific manifests and historical source hashes remain unchanged. The
  earlier STOP and pending-review entries above describe their original times.
- Starting HEAD was clean master at
  `d50b7e0c5cb329b7e12cf2fcba54c45aa50e41c7`; no repository AGENTS.md found.
  Ryan authorized closure documentation and an R1-F plan **for independent review
  only**, not implementation, model loading or data scoring.
- Saved `docs/plans/R1-F-PLAN.md`, explicitly PROPOSED / NOT APPROVED. It binds
  the reviewed E manifest/dev projection and historical source reconciliation,
  production runtime/configuration identity, dev-only scoring and valid-negative
  count gate, SPEC 10.4's exact strict 5% procedure, validated calibration
  application, durable interruption recovery and a committed pre-G freeze.
  Source-code changes must settle before dev scoring; the final scoring hash
  is not known or assumed equal to the historical B2 benchmark hash.
- Planning used local specifications/corrections, scorer/identity/loader and
  calibration interfaces, retained **metadata only**, lexicon bytes and prior
  synthetic benchmark evidence. Metadata shows 1,484 dev rows and 298 dev humans;
  the actual score-valid negative count is unknown until an approved F run.
  1% calibration remains disabled. No thresholds, scores or freeze were created.
- No network requests, model/weight loading, real-data selection/tokenization,
  dev/test scoring, inspection of test scores, calibration, test evaluation,
  UI work or dependency changes. Documentation references and whitespace are
  checked; runtime suites are not rerun for these documentation-only edits.
  R1-F and R1-G remain separate approval/review gates.

## 2026-11-01 — R1-F F0–F5 approval

- Ryan approved docs/plans/R1-F-PLAN.md at 3f3e787 and authorized F0–F5, including
  the specified local CUDA synthetic checks and development-only scoring.
  Stable implementation must be committed before scoring, and scores may not
  be retained under an old identity after hashed source changes.
- Explicit one-way digest binding: freeze -> calibration artifact digest.
  No artifact -> freeze digest or circular dependency. Preserve prepared data,
  historical source reconciliation and the narrow transfer-accounting exception;
  historical cumulative transfer compliance remains unproven.
- No test blobs/scores, network requests, reselection, tuning, CPU fallback,
  1% calibration, UI or new dependencies. Stop on plan identity/profile/numerical/
  reproducibility/count failures. Final validated freeze/evidence commit is
  submitted for independent review; R1-G remains unauthorized.
- F0/F1 implementation replaces permissive calibration lookup/placeholder
  application with strict schema/digest/profile matching and the exact distinct
  negative strict 5% rule. Nine normalized scorer sources now include calibration
  policy and dev runner; config, model/formula, loader and tokenization unchanged.
  Report Calibration projection is preserved; opt-in help/limitations no longer
  incorrectly say all text scores are uncalibrated. Default golden reports pass.
- Dev runner has no test split operation; metadata projection is fixed to the
  reviewed dev digest, data opens are restricted to its dev blobs, all Python
  socket connects/lookups and process launches are blocked during production
  work. Journal attempts/completions are durable and single-writer; incompatible,
  corrupt or terminal-failure resumes stop. Explicit truncated-tail recovery
  preserves original bytes and validates the prefix first. No outputs overwrite.
- Pure artifact/freeze tests enforce one-way digest binding, exact thresholds/
  ties/N, 1% refusal, invalid/ambiguous artifact diagnostics, profile/config/data/
  lexicon/source mismatches, report/CLI serialization and Git commit proof.
  Synthetic complete CLI pipeline tests use fake sessions/scorers, not models.
- F1 checks before real scoring: offline regression selection excludes six
  network/C2PA-control modules; 539 passed/21 deselected inside (16.90s), same
  outside (15.32s). A Unicode audit caught encoding drift in a rewritten Unicode
  fixture/docs; explicit UTF-8/escaped U+00E9 restored the intended semantics;
  61 identity tests passed (2.35s) after that repair. No production-source change
  after the full regression checks. Ruff/pip/whitespace pass; source audit10 files,
  one existing docstring inventory finding, zero violations. Exact commands and
  omissions are in r1f_implementation_verification.json. No real CUDA/model/dev
  scoring yet; next action is the required stable implementation commit.

## 2026-11-01 — R1-F execution on frozen source; freeze submitted for review

- Stable implementation committed **before any CUDA/model scoring** at
  `047421cf4c36f8a946453eacc1b9c056bf5147d6`. No hashed source edits followed.
  Configuration hash:
  `10f0fa316fa5f3d87c7819f86f09ecedc5bc5b1b71e9250d8586aece7390db2f`.
  F0/F1 tests/evidence are committed with that source; preparation sources,
  scorer math, model pins, loader, config and tokenization are unchanged.
- Two separate fresh-process CUDA preflights passed and matched exactly on
  full scoring fields/hash, implementation commit/source hashes, local asset
  manifest, committed B2 synthetic input and raw statistics/window. Actual
  profile: RTX 4060 Laptop GPU, driver572.60, CUDA12.4, torch2.6.0+cu124,
  transformers4.57.6, tokenizers0.22.2, eager/batch1/fp32, TF32 off/highest,
  deterministic algorithms true, CUBLAS_WORKSPACE_CONFIG=:4096:8, and settings
  applied before CUDA initialization. No unknown-driver/profile matching.
- Approved development procedure passed: all **1,484 rows valid**, **0 failed**,
  including **298 valid human negatives**, 298 clean machines and 888 attacks.
  No new exclusions, pair cleanup, reselection, refill, seed/profile changes or
  CPU fallback. The profile/settings and source/hash checks remained consistent.
  Every completion was durably journaled; no crash/resume was needed in the real
  run (interruption behavior is synthetic-test evidence only).
- The fixed first ten development-human IDs were repeated in a separate fresh
  development-model process after primary scoring (separate from the two
  synthetic processes) and matched all stored statistics/window/hash/identity
  fields exactly. This audit did not replace scores or increase N. Separate
  verify-dev passed full journal/input/final-ledger/count checks.
- Exact 5% threshold: **c=-0.9272342324256897** in r=-raw_score space, so flag
  iff raw_score **<0.9272342324256897**. Actual N=298; 14 strictly above c and
  1 tie at c (unflagged), empirical dev fraction14/298. 1% is disabled. Threshold
  is a distinct observed negative value, selected minimally under 20*k<=N;
  reversed-order independent assembly is byte-identical. This is not test FPR,
  a population-error guarantee, an origin probability or evidence of human origin.
- Artifact payload SHA-256:
  `3d779223c5c3779ff82ae1ce169b4c07ec59a3571b38b2d5463b28a8516be2c8`;
  artifact file SHA-256:
  `edd84087ab56d25d43df653cdaaaa2f06dccdb196108c32c67c9e1a505822134`.
  Freeze payload SHA-256:
  `48035a7984482a325349b32b746a3463534089849254141da61a2a019ce228aa`.
  Freeze -> artifact file/payload digests is one-way; the artifact has no freeze
  reference/digest. Freeze binds configuration, source, E/dev/reconciliation,
  score/failure ledgers, lexicon versions/hashes, quality sources and verification
  evidence. Source commit is embedded; the containing freeze Git commit is read
  back after commit, without a self-referential Git hash.
- Stored-score application/report replay passed on all 298 dev humans: actual
  artifact yields 14 strict supports_ai results, one unflagged tie, matching
  Calibration projection and lossless report round-trips. This replay used stored
  GPU scores/profile metadata; it was not a new forward pass or a new runtime
  profile measurement. It never accessed test scores or text.
- Every real preflight/score/audit phase and stored-score replay observed zero
  Python connections and zero forbidden data accesses. These are guarded-path
  observations, not OS/native network-isolation proof. The model/tokenizer files
  were hash-verified locally, without any network request/download or dependency
  change. The existing historical transfer exception remains unchanged and
  **historical cumulative transfer compliance remains unproven**.
- Primary recorded elapsed274.489s, CPU253.984s; GPU peak allocated5,854,253,568
  bytes, reserved6,188,695,552. First-ten audit reserved peak7,203,717,120 bytes.
  Exact receipts/resources/check commands/limitations are in r1f_verification.json.
  Full default/network-control tests, whole slow suite, CPU calibration, 1%,
  installed GPU portability, R1-G metrics/bootstrap/test scoring and UI are not run.
- R1-F artifacts/evidence/freeze are submitted for **independent review**, not
  marked independently accepted. R1-G requires reviewer confirmation of the
  committed freeze and separate authorization; no test blobs/scores were accessed.
