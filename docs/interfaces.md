# Interfaces

## Text scorer identity (R1-B1)

Implemented in `src/litmus/scorer/identity.py`; values from `src/litmus/config.py`
and the read-back execution profile (`src/litmus/scorer/loader.py::read_profile`).

### `scoring_config_hash`

`scoring_config_hash = SHA-256( canonical_json(fields) )`, where
`canonical_json` is `json.dumps(fields, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)` encoded as UTF-8. `fields` is a flat object with exactly
these keys:

**Addendum A4 fields and preprocessing policy** (static, `litmus.config`):
`scorer_version`, `formula_id`, `observer_repo`, `observer_commit`,
`performer_repo`, `performer_commit`, `tokenizer_json_sha256` (computed from
the local file at load and required to equal the pinned value),
`add_special_tokens`, `split_special_tokens`, `truncation_side`, `max_tokens`,
`min_tokens`, `weight_dtype`, `reduction_dtype`, `score_direction`,
`preprocessing_version`.

**Numerical execution profile** (read back at runtime, never the requested value):
`device_type`, `gpu_name`, `nvidia_driver_version` (via NVML, no subprocess),
`cuda_runtime` (`torch.version.cuda`), `torch_version`, `transformers_version`,
`tokenizers_version`, `attn_implementation` (from both loaded model configs),
`batch_size`, `matmul_allow_tf32`, `cudnn_allow_tf32`,
`float32_matmul_precision`, `deterministic_algorithms`,
`cublas_workspace_config`, `weight_dtype` (from the loaded parameters),
`reduction_dtype`, `os_family`, `cuda_initialized_before_settings` (whether
`torch.cuda.is_initialized()` was already true when the numerical settings were
applied; see the initialization-order rule).
The read-back `weight_dtype` / `reduction_dtype` must equal the configured
values, otherwise hashing is refused. On CPU, GPU-only fields are
`"not_applicable"`.

**Source identity**: `source_files` (the list below) and `source_sha256`.

### Source file list and `source_sha256`

```
src/litmus/config.py
src/litmus/ingestion.py
src/litmus/scorer/analyzer.py
src/litmus/scorer/binoculars.py
src/litmus/scorer/identity.py
src/litmus/scorer/loader.py
src/litmus/scorer/tokenize.py
```

`analyzer.py` and `identity.py` were added in the R1-B1 corrections: they decide
completeness, the reported result and the hash itself.

For each path in sorted order: `entry = path + "\n" + sha256(file bytes with
CRLF replaced by LF)`. `source_sha256 = SHA-256( UTF-8( "\n".join(entries) ) )`.
CRLF→LF normalization applies only to these files. The list itself is also a
hash field (`source_files`).

### Required-field schema and completeness (Corrections A CA2; R1-B1 corrections)

Implemented as `PROFILE_SCHEMA` / `profile_failures()` in
`src/litmus/scorer/loader.py`. The profile must have exactly these keys:

| Field | Permitted value on `cuda` | On `cpu` |
|---|---|---|
| `device_type` | `"cuda"` or `"cpu"` | same |
| `gpu_name` | non-empty string | `"not_applicable"` |
| `nvidia_driver_version` | string matching `\d+(\.\d+)+` (e.g. `572.60`) | `"not_applicable"` |
| `cuda_runtime` | string matching `\d+\.\d+` (e.g. `12.4`) | `"not_applicable"` |
| `cublas_workspace_config` | `":4096:8"` | `"not_applicable"` |
| `torch_version`, `transformers_version`, `tokenizers_version` | string matching `\d+(\.\d+)+` plus an optional local/pre-release suffix (e.g. `2.6.0+cu124`) | same |
| `attn_implementation` | `"eager"` | same |
| `batch_size` | int `1` | same |
| `matmul_allow_tf32`, `cudnn_allow_tf32` | bool `false` | same |
| `float32_matmul_precision` | `"highest"` | same |
| `deterministic_algorithms` | a bool | same |
| `weight_dtype`, `reduction_dtype` | `"float32"` | same |
| `os_family` | `"Windows"`, `"Linux"` or `"Darwin"` | same |
| `cuda_initialized_before_settings` | bool `false` | same |

`"not_applicable"` is permitted only for the four GPU-specific fields, and only on
CPU. The profile is **incomplete** if any of these holds: it is empty; a key is
missing; an extra key is present; a value is `None`, an empty or blank string,
`"unavailable"` or `"unknown"`; a value is outside its permitted set; or a
model setting (`attn_implementation`, `weight_dtype`) differs from the value
read from either loaded model.

An incomplete profile gives `inconclusive` with reason
`execution_profile_incomplete`, and `details.execution_profile_failures` maps
each failing field to its reason. It never matches a calibration, even one
carrying the same hash. If the profile cannot be hashed (for example, a missing
key), `scoring_config_hash` is `null`.

### Initialization-order rule

`configure_numerics(device_type)` is the one function that applies every
numerical setting: `CUBLAS_WORKSPACE_CONFIG` (on CUDA with deterministic
algorithms), both TF32 flags, float32 matmul precision, and deterministic
algorithms. It must run **before** any CUDA or cuBLAS initialization. It records
`torch.cuda.is_initialized()` as observed by the first call in the process for
that device type. A later call cannot overwrite this record.

Reading back the environment variable is not proof that it took effect, because
cuBLAS reads it once, when cuBLAS initializes. If CUDA was already initialized
when the settings were applied, or if no configuration ran (order cannot be
established), then `cuda_initialized_before_settings` is not `false`. The
profile is then incomplete, with the additional reason
`cuda_initialized_before_settings`. There is no workaround, and analysis never
starts subprocesses.

**Re-read before scoring:** immediately before each scoring call, the analyzer
re-reads the effective settings: both TF32 flags, matmul precision, the
deterministic flag, `cublas_workspace_config`, and each model's attention
implementation and weight dtype. It compares them with the profile that was
hashed, and never re-applies them. On any difference the result is
`inconclusive` with reason `execution_profile_changed` and no `raw_score`, and
`details.execution_profile_changes` lists each field as `{profile, effective}`.

### Calibration matching

Strict: a calibration file in `calibrations/*.json` applies only if its
`scoring_config_hash` equals the runtime hash exactly. In R1-B1 no calibration
files exist, every run is uncalibrated (`inconclusive`, reason
`no calibration for this configuration`), and CPU runs are always uncalibrated.
Threshold application is not implemented (R1-F); a matching file would yield
`calibration_application_not_implemented`.

### OriginEvidence emitted by the text analyzer (`method_id = "binoculars"`)

`raw_score = B`, `score_direction = "lower_means_more_machine"`,
`calibration = null`, `result = "inconclusive"`, plus `details`:
`scored_window` (`tokens_total`, `tokens_scored`, `truncated`,
`scored_char_range` in code points), `nll_performer`, `xent`, `n_input_tokens`,
`n_target_tokens`, `tokenizer_vocab_size`, `model_output_dim`,
`scoring_config_hash`, `scoring_config` (the hashed fields, which include the
execution profile), `execution_profile_complete`, `execution_profile_failures`.

## Text quality observations (R1-C2)

Opt-in, model-free observations of what a text segment contains. **Quality
observations do not establish AI origin and never affect origin results.**

### `--quality {off,on}`

- `off` (the default): no observer is constructed or run. The report is
  byte-identical to the report without quality support: every segment has
  `"quality": []` and `limitations` is unchanged (checked against the golden
  files; `--quality off` output equals the output with the flag omitted).
- `on`: the four observers are constructed (lexicons loaded and validated)
  before analysis starts. Origin evidence is computed first; then each **text**
  segment gets four observations, in the order below, from its decoded text
  alone. Image segments keep `"quality": []`. The report's `limitations` gains
  the quality limitations (`report.QUALITY_REPORT_LIMITATIONS`), including
  "quality observations do not establish AI origin and never affect origin
  results", "quality lexicons are English-oriented and provisional (v1)" and
  "quality word counts assume space-separated scripts; ...".

### Observer IDs (`observer_version = "1"`)

| `observer_id` | What is counted |
|---|---|
| `stock_phrases` | matches of the packaged `stock_phrases` lexicon |
| `hedges` | matches of the packaged `hedges` lexicon |
| `repeated_word_3grams` | every occurrence of a word 3-gram whose casefolded key occurs at least twice (consecutive words of the word index; crosses punctuation and line breaks; no stop-word filtering) |
| `claim_phrases_to_inspect` | matches of the packaged `claim_phrases_to_inspect` lexicon |

Lexicon matching is case-insensitive on the original text, leftmost-longest
and non-overlapping, with word-boundary lookarounds (R1-C1 entry compiler).

### Record fields

- `count`: exact number of matches (never capped).
- `status`: `observed` if `count > 0`, else `none_found`; `error` on failure.
- `rate_per_100_words`: `count / words * 100`, where `words` is the word-index
  count of the segment text; `null` when the text has zero words.
- `spans`: `[start, end)` code-point offsets into the decoded segment text, in
  order; at most **1,000** (the span cap) are listed.

### `notes` format

Fixed `key=value` strings, in this order:

1. `observer_version=1`
2. lexicon observers only: `lexicon_name=<name>`, `lexicon_version=<n>`,
   `lexicon_sha256=<sha256 of the packaged file bytes>`
3. `spans_truncated=true|false` (true when `count` exceeds 1,000), then
   `spans_reported=<number of spans listed>`
4. `claim_phrases_to_inspect` only:
   `label=phrase to inspect; not evidence that a claim is unsupported`

### Error behavior

Each observer runs in its own `try/except`. An exception yields that
observer's record with `status = "error"`, `count = null`,
`rate_per_100_words = null`, `spans = []` and notes
`["observer_version=1", "error=<exception class name>"]`; the other observers'
records and the origin evidence are unchanged, and the CLI still exits 0. A
packaged lexicon that fails validation gives the same error record with the
note `lexicon_invalid=<reason>` instead of `error=...`.

Lexicon loading happens when the observers are constructed (before analysis),
separately for each lexicon observer. A `LexiconError` gives that observer
`lexicon_invalid=<reason>` (a resource missing at the file read is reported as
`lexicon_invalid=lexicon '<name>' is not packaged`). An `OSError` or any
subclass (for example `PermissionError`) gives that observer
`error=<exception class name>`. In both cases the other observers, origin
evidence and the report are unaffected, and the CLI exits 0. Any other
exception during lexicon loading is not caught: it propagates out of the CLI
(traceback, exit 1) before analysis starts.
