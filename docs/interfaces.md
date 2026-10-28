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
`reduction_dtype`, `os_family`.
The read-back `weight_dtype` / `reduction_dtype` must equal the configured
values, otherwise hashing is refused. On CPU, GPU-only fields are
`"not_applicable"`.

**Source identity**: `source_files` (the list below) and `source_sha256`.

### Source file list and `source_sha256`

```
src/litmus/config.py
src/litmus/ingestion.py
src/litmus/scorer/binoculars.py
src/litmus/scorer/loader.py
src/litmus/scorer/tokenize.py
```

For each path in sorted order: `entry = path + "\n" + sha256(file bytes with
CRLF replaced by LF)`. `source_sha256 = SHA-256( UTF-8( "\n".join(entries) ) )`.
CRLF→LF normalization applies only to these files. The list itself is also a
hash field (`source_files`).

### Incomplete profile (Corrections A, CA2)

A profile value that cannot be determined is recorded as `"unavailable"`. Such a
profile is **incomplete**: the analyzer returns `inconclusive` /
`execution_profile_incomplete` and never looks up a calibration.

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
execution profile), `execution_profile_complete`.
