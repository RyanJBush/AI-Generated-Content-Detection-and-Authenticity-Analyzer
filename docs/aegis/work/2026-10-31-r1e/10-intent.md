# R1-E execution intent

Authority: Ryan's 2026-10-31 approval of R1-E-PLAN.md and bounded acquisition.
Parent specification: docs/plans/R1-E-PLAN.md. This process note does not amend it.

Outcome: verified CA1; one approved train.csv acquisition; metadata-only selection
of up to 1,000 source groups at seed 20261030; tokenizer-only eligibility,
dedup/cleanup; repeatable manifests and verification; commit for independent review.

Boundary: no scoring, weights, CUDA, calibration, test evaluation, UI, dependencies,
paid services, raw-text publication, mutable-revision fallback or refill.
Limits: 13 GB cumulative payload, at least 30 GB free before acquisition,
25 GB incremental artifacts. Stop on identity/schema/budget/reproduction failure.

Baseline: master at d7ed91fc949087cee271ac51dcc058bc2a115f48. Preserve the five
pending Markdown documents from the previous planning task. Read-set: approved
E plan/request, R1-PLAN and Corrections A, current decisions, config/tokenize,
repository status and prior evidence. No repository AGENTS.md found.

Verification: synthetic guard/key/selection/cleanup/manifest tests; local-tokenizer
guard check; actual acquisition length/hash; full-file preparation and repeat;
raw-backed manifest verification; inside/outside default tests, Ruff, pip check,
whitespace and scoped source audit. No inference of completion from prior recaps.
