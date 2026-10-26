# Shared interfaces (Claude Code ↔ Codex)

Status: contract as of the commit that adds this file. Claude Code builds Blocks 1–3, 5, 6; Codex builds Block 4
(SPEC §5). **No item below changes without Ryan coordinating it first.** Items marked *existing* are in the
repository now; items marked *planned* are additions this task will implement exactly as written here, without
changing anything existing. A planned item that turns out to need a different shape is a change and goes back to
Ryan before it is made.

Open question for Ryan: the task message names the calibration file `calibration/<pair_id>.json`; SPEC §3.1/§4 key
it by `calibration/<scoring_config_hash>.json`. This document follows SPEC until Ryan decides (§4 below).

## 1. Scorer API — `src/litmus/binoculars.py` (*existing*, frozen)

Pure tensor math, no model loading. Verified at `08a8d98`; validation added at `e5e4046`.

```python
binoculars_statistics(observer_logits, performer_logits, input_ids, attention_mask) -> dict[str, Tensor]
validate_statistics(stats) -> None          # raises NumericalScoringError
class NumericalScoringError(ValueError)
```

- Inputs: logits `[B, T, V]` (same shape for both models; V = full output dimension, never trimmed), `input_ids`
  `[B, T]`, `attention_mask` `[B, T]` of 0/1, right-padded. Role order is (observer = base, performer = instruct).
- Output keys, each a `[B]` tensor: `nll_performer`, `nll_observer`, `xent`, `score` (float32), `n_input_tokens`,
  `n_scored_tokens` (integer).
- Raises `ValueError` on shape/mask/ID problems or a document with < 2 real tokens; raises `NumericalScoringError`
  (subclass of `ValueError`) unless NLL_perf ≥ 0, NLL_obs ≥ 0, XENT > 0 and B are all finite.
- Math: SPEC §3.1 (shifted numerator with `m_t = a_t·a_{t+1}`; denominator over all real positions incl. the final
  one; float32 log-softmax and reductions).

## 2. Model-loading wrapper — `src/litmus/scoring.py` (*planned*)

Kept separate from `binoculars.py` so the verified math file is unchanged (deviation from the SPEC §4 layout
comment "Layer A math + model loading"; recorded here and in §12 of the handoff).

```python
load_pair(pair: str = config.DEFAULT_PAIR, device: str = "auto", dtype: str = "float32") -> ModelPair
score_texts(texts: list[str], pair: ModelPair, batch_size: int = 1) -> list[ScoreResult]
score_text(text: str, pair: ModelPair) -> ScoreResult
```

- `ModelPair` (dataclass): `observer`, `performer` (eval-mode models), `tokenizer` (the observer's), `pair` (key of
  `config.PAIRS`), `observer_id`, `performer_id` (`"name@revision"`), `device` (`"cuda"`/`"cpu"`), `weight_dtype`
  (`"float32"`/`"bfloat16"`/`"float16"`), `tokenizer_sha256` (SHA-256 of the observer's `tokenizer.json`),
  `attn_implementation`. `load_pair` raises if observer and performer `tokenizer.json` bytes differ or their output
  dimensions differ. `device="auto"` resolves to `"cuda"` if available, else `"cpu"`.
- Tokenization: observer tokenizer at its pinned revision, `add_special_tokens=False`, `split_special_tokens=False`,
  no chat template, raw text unmodified; right truncation to `config.MAX_LENGTH` (512); right padding with the
  tokenizer's pad token for batches; masking by `attention_mask` only.
- `ScoreResult` (dataclass): `status` (`"ok"` | `"too_short"` | `"error"`), `n_tokens` (untruncated), `n_input_tokens`,
  `n_scored_tokens`, `truncated` (bool), `nll_performer`, `nll_observer`, `xent`, `score` (float or `None`),
  `error` (str or `None`).
  - `too_short`: `n_tokens < config.MIN_INPUT_TOKENS` (64); all statistics `None`; models not run for that text.
  - `error`: a `NumericalScoringError` for that text; statistics `None`; the message is kept in `error`.
- Batch sizes > 1 are supported but the drift/benchmark evidence so far is batch size 1 only.

## 3. Configuration and identity — `src/litmus/config.py`, `src/litmus/identity.py`

*Existing* in `config.py`: `OBSERVER_REVISION = None`, `PERFORMER_REVISION = None` (unset until Ryan selects a pair),
`MODEL_REVISIONS` (four pinned Qwen2.5 commit SHAs), `ADD_SPECIAL_TOKENS = False`, `PADDING_SIDE = "right"`,
`TRUNCATION_SIDE = "right"`, `MAX_LENGTH = 512`, `REDUCTION_DTYPE = "float32"`.

*Planned* additions to `config.py` (nothing existing is renamed or removed):

```python
SCORER_VERSION = "1"            # bump on any change to scoring math, tokenization or masking
PREPROCESSING_VERSION = "none-1"  # no text-altering normalization (SPEC §3.4)
SPLIT_SPECIAL_TOKENS = False
MIN_INPUT_TOKENS = 64
PAIRS = {"0.5b": ("Qwen/Qwen2.5-0.5B", "Qwen/Qwen2.5-0.5B-Instruct"),
         "1.5b": ("Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-1.5B-Instruct")}
DEFAULT_PAIR = "0.5b"           # provisional: the only pair measured so far; Ryan's selection (D4/D11) overrides
```

*Planned* `src/litmus/identity.py`:

```python
canonical_json(obj) -> bytes     # json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False), UTF-8
sha256_hex(data: bytes) -> str
compute_identity(pair: ModelPair) -> dict
```

`compute_identity` returns `{"scoring_identity": {...}, "scoring_identity_hash": str, "execution_profile": {...},
"execution_profile_hash": str, "scoring_config_hash": str, "environment": {...}}`:

- `scoring_identity` (SPEC §3.1): observer/performer `name@revision`; `tokenizer_sha256`; tokenizer settings
  (`add_special_tokens`, `split_special_tokens`, padding/truncation side, `max_length`, `chat_template: null`);
  `min_input_tokens`; positional/masking rule strings; `reduction_dtype`; `scorer_version`; `preprocessing_version`;
  SHA-256 of `src/litmus/binoculars.py`, `scoring.py`, `config.py`, `identity.py` (relative paths as keys; bytes
  hashed after converting CRLF to LF so Windows and Linux checkouts agree).
- `execution_profile`: `weight_dtype`; `device` (`cuda`/`cpu`); `torch` version and `torch.version.cuda`;
  `transformers` and `tokenizers` versions; `attn_implementation`; `cuda_matmul_allow_tf32`, `cudnn_allow_tf32`,
  `float32_matmul_precision`; SHA-256 of `requirements.lock` (CRLF→LF).
- `*_hash` = `sha256_hex(canonical_json(section))`; `scoring_config_hash` =
  `sha256_hex(canonical_json({"scoring_identity_hash": ..., "execution_profile_hash": ...}))`.
- `environment` (recorded, **not** hashed): OS/platform, Python version, GPU name, driver-reported CUDA, CPU threads.
  Timestamps and absolute paths are never included in hashed sections.

## 4. Calibration file — `calibration/<scoring_config_hash>.json` (*planned*; Codex writes, CLI/app read)

No calibration file exists yet. Path per SPEC §3.1/§4 (see the open question at the top).

```json
{
  "format_version": 1,
  "scoring_config_hash": "…", "scoring_identity_hash": "…", "execution_profile_hash": "…",
  "pair": {"observer": "name@rev", "performer": "name@rev"},
  "weight_dtype": "float32",
  "dev_manifest_sha256": "…",
  "counts": {"human_rows": 0, "source_groups": 0},
  "selection_rule": "free text describing the conservative empirical FPR rule (SPEC §7.2)",
  "detectors": {
    "binoculars":    {"direction": "lower_is_machine", "thresholds": {"fpr_0.01": {"threshold": 0.0, "achieved_dev_fpr": 0.0}, "fpr_0.05": {"threshold": 0.0, "achieved_dev_fpr": 0.0}}},
    "nll_performer": {"direction": "…", "thresholds": {"fpr_0.01": {…}, "fpr_0.05": {…}}},
    "nll_observer":  {"direction": "…", "thresholds": {"fpr_0.01": {…}, "fpr_0.05": {…}}},
    "length":        {"direction": "…", "thresholds": {"fpr_0.01": {…}, "fpr_0.05": {…}}}
  }
}
```

Reader rules (`src/litmus/calibration.py`, *planned*): the CLI/app look only for
`<calibration_dir>/<current scoring_config_hash>.json`. It is **valid** only if it parses, `format_version == 1`,
all three hashes equal the current identity, `detectors.binoculars.direction == "lower_is_machine"`, and
`t_strict = fpr_0.01.threshold` and `t_primary = fpr_0.05.threshold` are finite with `t_strict ≤ t_primary`.
Otherwise the report flag is `no_calibration` (raw scores still shown), with the reason recorded. Baseline
detector thresholds are evaluation artifacts and are never used for app flags. `artifact_sha256` in the report is
the SHA-256 of the file bytes as read.

## 5. Report JSON — SPEC §3.3 (*planned* `src/litmus/report.py`)

`build_report(text, score_result, slop_result, identity, calibration_status) -> dict`; `report_to_json(report) -> str`
(UTF-8, `ensure_ascii=False`, indent 2). Fields exactly as SPEC §3.3, with these specifics:

- `version`: `"0.3.2"` (SPEC version); `scorer_version`, `preprocessing_version`, the three hashes from §3.
- `models`: `observer`, `performer` (`name@rev`), `tokenizer_sha256`, `weight_dtype`.
- `n_tokens`, `n_input_tokens`, `n_scored_tokens`, `truncated` from `ScoreResult`.
- `binoculars`: `nll_performer`, `xent`, `score`, `baselines.nll_observer` (numbers, or `null` when unavailable);
  `flag` ∈ `flagged | uncertain_abstain | not_flagged | no_calibration | too_short`, or `null` when `error` is set;
  `flag_text` (human wording; `not_flagged` → "score did not cross the calibrated threshold"); `error`
  (`null` or message — numerical failure is an explicit error, not a flag); `calibration` (`null` unless valid,
  else the SPEC §3.3 object incl. `t_strict`, `t_primary`, `source: "clean human dev rows"`);
  `calibration_status` (`{"valid": bool, "reason": str, "path": str}` — reason when absent/invalid);
  `note` (the SPEC "not a probability" sentence).
- Flag policy (SPEC §3.3): `B < t_strict` → `flagged`; `t_strict ≤ B < t_primary` → `uncertain_abstain`;
  `B ≥ t_primary` → `not_flagged`. Without valid calibration → `no_calibration`. `too_short` takes precedence.
- `slop`: `n_words`, and `features` with keys `stock_phrases`, `hedges`, `repeated_ngrams`, `inspect_phrases`, each
  `{"count": int, "rate": float|null, "spans": [[start, end], …], "matches": [str, …]}`; `rate` is per 100 words
  (`null` when `n_words == 0`); `matches[i]` is the lexicon entry or 3-gram for `spans[i]`. Offsets index the
  original string (`text[start:end]`).
- `disclaimer`: fixed text stating the tool reports evidence, not verdicts, and must not be the sole basis for
  academic, employment, or moderation decisions.

## 6. Layer B inputs — `data/lexicons/*.txt` (*planned*)

`stock_phrases.txt`, `hedges.txt`, `inspect_phrases.txt`: UTF-8, one entry per line, `#` comment header (source:
author-written; version). Their SHA-256s go into the freeze file (§7.2, Codex). Editing a lexicon after freeze is
forbidden.

## 7. Packaging — `pyproject.toml`, `requirements.lock`

*Existing*: `pyproject.toml` project `litmus` 0.1.0, dependencies `torch, transformers, numpy, scipy, gradio`
(unpinned), setuptools build; `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `pythonpath = ["src"]`,
marker `slow`, `addopts = "-m 'not slow'"`. `requirements.lock`: 69 pinned packages (e.g. `torch==2.6.0+cu124`,
`transformers==5.20.2`, `tokenizers==0.23.3`, `gradio==6.30.0`, `pytest==9.1.1`, `ruff==0.17.2`).

*Planned* addition to `pyproject.toml`: `[project.scripts] litmus = "litmus.cli:main"`. No dependency changes;
`requirements.lock` unchanged. Tests that download or load models carry `@pytest.mark.slow`; Codex's tests follow
the same rule.
