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
hand-edited); this file carries their status.

## Per-artifact status

| Artifact | SHA-256 (at `10d6103`) | Generating script | Status | Reason |
|---|---|---|---|---|
| `eval/results/tokenizer_checks.json` | `fdc593e5944fea3154d364f409898b7604740f2e6b7ee4420edf08c623d78227` | `tests/tokenizer_probe.py` | **Superseded / incomplete** | Revisions recorded as `main`, not commit SHAs; no `tokenizer.json` hashes; vocabulary compared by length only; no omitted-default case; no attention masks; `<\|im_start\|>` fixture missing; output-logit dimension not checked. |
| `eval/results/benchmark_0_5b.json` | `f65f0e7fe3db0a5addb17d32d639686ae434e49fa09d5e5adfd6e3fed4800e41` | `eval/benchmark_0_5b.py` | **Invalid** | Not fp32: `from_pretrained` was called without `dtype`, which in transformers 5.20.2 resolves to `"auto"` and the 0.5B-Instruct config's `bfloat16`. Performer only (observer never loaded). Reduction is the performer's own entropy, not observer→performer cross-entropy; no NLL. Load time not measured; one run per length; no host memory. |
| `eval/results/runtime_drift.json` | `b670487e0862a844b847a89a65a01951ad5cc5bf211399373fc697079c2a15d6` | `eval/drift_probe.py` | **Invalid** | "nll" indexes `log_probs[0, :-1, ids[0, 1:]]`, a (T−1)×(T−1) matrix, and averages all of it (not per-position targets). "xent" is the performer's negative entropy (hence negative XENT and B). Performer only. Two 10-token texts (below the 64-token minimum); GPU only; no repeats or delta summaries. |
| `eval/results/logs/hf_check.log` | `1068d39b8af13e7fe598e7622123914f112adb1454fa300be1190a52f14bdd12` | `eval/hf_check.py` | **Unverified assertion** | The script prints two hard-coded sentences and performs no check. "16GB RAM, 2 vCPU" and "feasible on free tier" are not measurements and are not deployment evidence. |
| `eval/results/logs/*.log` (others) | see `git show 10d6103 --stat` | — | Corroboration only | Contain progress bars and warnings, no results. |

## Not run

| Claim | Status |
|---|---|
| 1.5B pair runtime/memory | **Not run** (weights never downloaded; no artifacts) |
| 0.5B fp32 runtime/memory | **Not run** (the existing benchmark ran bf16) |
| Observer (base) model forward pass | **Not run** |
| Deployment (HF Space) feasibility | **Not run** |
| CPU vs GPU drift | **Not run** |

Replacement measurements will be produced only through the Task 2 scorer after its math is reviewed.
