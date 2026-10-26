# SUPERSEDED: Task 1 outputs from commit 10d6103

Preserved unedited. Do not use any value here as evidence. Full per-artifact reasons: `docs/results-status.md`.

| File | Status | Replaced by |
|---|---|---|
| `benchmark_0_5b.json` | **Invalid**: ran bf16 (not fp32), performer only, simulated reduction (performer entropy, no NLL) | `eval/results/benchmark_0.5b_float32.json` (production scorer, both models, fp32) |
| `runtime_drift.json` | **Invalid**: wrong NLL indexing, XENT is performer negative entropy, performer only | `eval/results/runtime_drift.json` (production scorer, both models, 20 texts) |
| `tokenizer_checks.json` | **Superseded / incomplete**: unpinned revisions, no hashes, no masks, missing fixtures | `eval/results/tokenizer_checks.json` |
| `logs/hf_check.log` | **Unverified assertion**: two hard-coded printed sentences, no check performed | Nothing; deployment feasibility is **not run** |
| `logs/*` (others) | Corroboration only; no results; exit codes never captured (`$LASTEXITCODE` literal) | — |

Generating scripts are in commit `277397d`. `eval/benchmark_0_5b.py` and `eval/drift_probe.py` were retired
(removed from the working tree) when the production-scorer benchmark was added.
