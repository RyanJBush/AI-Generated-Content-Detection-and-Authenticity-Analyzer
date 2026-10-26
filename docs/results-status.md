# Status of Task 1 outputs in `eval/results/`

Checkpoint A has **not** passed. D11 and D12 remain **Open**.

## Provenance

The outputs below were committed in `10d6103` (2026-10-26 13:27:53 -0400). The scripts that produced them were
untracked at that commit and were first committed afterwards, unchanged, in the commit that adds this file.
File modification times on the builder machine precede each run's recorded start time, which is consistent with
these being the generating scripts, but this does not prove it. No log records the command line, and every
`*_meta.log` contains the literal string `ExitCode: $LASTEXITCODE` (exit status was never captured). No raw log
contains any of the numbers in the JSON files.

These outputs do not establish checkpoint A completion. They are preserved unedited (generated files are never
hand-edited) under `eval/results/superseded/10d6103/`, moved there by `git mv`; this file carries their status.
The SHA-256 values below are unchanged by the move.

## Per-artifact status

| Artifact | SHA-256 (at `10d6103`) | Generating script | Status | Reason |
|---|---|---|---|---|
| `eval/results/superseded/10d6103/tokenizer_checks.json` | `fdc593e5944fea3154d364f409898b7604740f2e6b7ee4420edf08c623d78227` | `tests/tokenizer_probe.py` (now `eval/tokenizer_checks.py`) | **Superseded / incomplete** — replaced by `eval/results/tokenizer_checks.json` from the pinned rewrite | Revisions recorded as `main`, not commit SHAs; no `tokenizer.json` hashes; vocabulary compared by length only; no omitted-default case; no attention masks; `<\|im_start\|>` fixture missing; output-logit dimension not checked. |
| `eval/results/superseded/10d6103/benchmark_0_5b.json` | `f65f0e7fe3db0a5addb17d32d639686ae434e49fa09d5e5adfd6e3fed4800e41` | `eval/benchmark_0_5b.py` | **Invalid** | Not fp32: `from_pretrained` was called without `dtype`, which in transformers 5.20.2 resolves to `"auto"` and the 0.5B-Instruct config's `bfloat16`. Performer only (observer never loaded). Reduction is the performer's own entropy, not observer→performer cross-entropy; no NLL. Load time not measured; one run per length; no host memory. |
| `eval/results/superseded/10d6103/runtime_drift.json` | `b670487e0862a844b847a89a65a01951ad5cc5bf211399373fc697079c2a15d6` | `eval/drift_probe.py` | **Invalid** | "nll" indexes `log_probs[0, :-1, ids[0, 1:]]`, a (T−1)×(T−1) matrix, and averages all of it (not per-position targets). "xent" is the performer's negative entropy (hence negative XENT and B). Performer only. Two 10-token texts (below the 64-token minimum); GPU only; no repeats or delta summaries. |
| `eval/results/superseded/10d6103/logs/hf_check.log` | `1068d39b8af13e7fe598e7622123914f112adb1454fa300be1190a52f14bdd12` | `eval/hf_check.py` | **Unverified assertion** | The script prints two hard-coded sentences and performs no check. "16GB RAM, 2 vCPU" and "feasible on free tier" are not measurements and are not deployment evidence. |
| `eval/results/superseded/10d6103/logs/*.log` (others) | see `git show 10d6103 --stat` | — | Corroboration only | Contain progress bars and warnings, no results. |

## Not run

| Claim | Status |
|---|---|
| 1.5B pair runtime/memory | **Not run** (weights never downloaded; no artifacts) |
| Deployment (HF Space) feasibility | **Not run** |
| 0.5B bf16/fp16 runtime/memory (benchmark) | **Not run** (bf16/fp16 appear only in drift probes) |
| CPU bf16/fp16 drift | **Not run** (not requested) |

## Current outputs

| Artifact | Script | Status |
|---|---|---|
| `eval/results/tokenizer_checks.json` + `logs/tokenizer_checks*.log` | `eval/tokenizer_checks.py` | Provisional Task 1 measurement at pinned revisions; command and exit code in the meta log. Not yet reviewed. |
| `eval/results/benchmark_0.5b_float32.json` + `logs/benchmark_0.5b_float32*.log` | `eval/benchmark.py` | Provisional Task 1 measurement: pinned 0.5B observer + performer, fp32 weights, production scorer, batch 1, 64–512 tokens. Not yet reviewed. A first run with two measurement defects is preserved in `eval/results/superseded/benchmark_0.5b_float32_run1/`. |
| `eval/results/runtime_drift.json` + `logs/runtime_drift*.log` | `eval/drift.py` | Provisional D11 drift screening: 20 fixture texts (`eval/fixtures/drift_texts.json`, SHA-256 `d00442ca9bb69b9f3b2e5905438bf8e9dac10a1dca8704f31d4e5141905f4cfc`), pinned 0.5B pair, GPU fp32 (reference) / bf16 / fp16 and CPU fp32, 2 repeats each, production scorer. Not calibration or threshold-portability evidence. Known labelling artifact: when every difference is 0, `max_at_text` reports the last text ID (`d20`) from tie-breaking; it carries no information. Not yet reviewed. |

`eval/benchmark_0_5b.py` and `eval/drift_probe.py` are retired (removed; in history at `277397d`).

## Line-ending note (2026-10-26)

Files under `eval/fixtures/**` and `eval/results/**` are now `-text` (`.gitattributes`, docs/interfaces.md §8): the
stored blobs are the exact working bytes, so every recorded SHA-256 above reproduces on any checkout. Contents are
unchanged apart from line endings in the stored blobs, but their git blob IDs changed. In particular
`runtime_drift.json` records `git_blob` `3305f490134ce1d20703fbf7ab2ea57643d81107` for `eval/fixtures/drift_texts.json`
(the LF blob at `023bfac`); from `f607360` on, the blob is `80234e8e4f358481c41621f8c1b8a2dc001ef66b`. The recorded SHA-256
`d00442ca9bb69b9f3b2e5905438bf8e9dac10a1dca8704f31d4e5141905f4cfc` is unchanged and is the identity to check.
