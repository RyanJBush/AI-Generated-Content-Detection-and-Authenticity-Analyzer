# R1-E execution evidence index

Closure (2026-11-01): Ryan supplied independent Codex review of d50b7e0 and
instructed R1-E closure with the same narrow historical uncertainty exception.
Historical cumulative transfer compliance remains unproven. The following
pending-review/STOP statuses are historical, not the current closure state.

Follow-up status: Ryan accepted the specific historical uncertainty (not cap
compliance) and authorized an offline correction; R1-E remains pending independent
review. New evidence: eval/results/r1e_budget_fix_verification.json,
r1e_budget_fix_source_reconciliation.json and r1e_budget_fix_source_verification.json.
Original execution status below describes b2d24da and is preserved historically.

Follow-up evidence strength: correction target/RAID regression 68 passed inside
and outside, Ruff/pip/Unicode/whitespace pass; exact source reconciliation and
original-evidence preservation pass on existing outputs. No live-network proof
was attempted; original transfer-cap compliance remains unknown. Confidence B
for this bounded offline correction, no acceptance claim for R1-E. The full
default suite with loopback controls and real selection reconstruction were not
rerun. Work is submitted via the containing follow-up commit; repository/commit
receipt is reported after Git readback, with no task-created branch/worktree.

Status: STOP, not complete/accepted: redirect bodies bypass acquisition counters;
the cumulative transfer cap is not proven. Actual overrun is not established.
Primary/repeat preparation and final read-only verifier passed.
Authority: Ryan's 2026-10-31 E0–E6 and bounded acquisition approval.
Baseline: d7ed91fc949087cee271ac51dcc058bc2a115f48 on master.
No task-created branch or worktree. Commit scope: mixed implementation/evidence/docs.

- CA1: eval/results/r1e_ca1.json (303/1,000 synthetic dev; fixed seed).
- API/acquisition: eval/manifests/r1e/preflight.json and acquisition.json.
- Scientific records: eval/manifests/r1e/primary/ and repeat/ (seven files each).
- Real run telemetry/guards: eval/results/r1e_primary_run.json,
  r1e_repeat_run.json, r1e_primary_guards.json and r1e_repeat_guards.json.
- Final raw-backed/repeat comparison: eval/results/r1e_primary_verification.json.
- Consolidated checks, resources, limitations and changed paths:
  eval/results/r1e_verification.json.
- Source Unicode audit: eval/results/r1e_non_ascii_audit.json.
- Stop-condition reproduction: eval/results/r1e_redirect_budget_audit.json
  (23 synthetic redirect-body bytes read, durable counters unchanged, no network).
- Governing procedure/actual outcomes: docs/plans/R1-E-PLAN.md,
  docs/interfaces.md and the 2026-10-31 decision entries.

Boundary held: 973 groups/4,845 rows, 298 dev humans; no raw-text Git inclusion,
weights, CUDA, scoring, calibration, test evaluation or new dependencies.
The development count gate alone does not authorize R1-F or establish score validity.
Pending independent review is distinct from execution verification or R1-E closure.

Baseline alignment: approved E plan and Corrections A, source-unique metadata
selection and independent grouped split preserved; production defaults unchanged.
Complexity control: standalone preparation modules and scripts own acquisition,
selection, tokenization, cleanup and verification; no production analyzer integration,
fallback artifact, duplicated scoring logic or compatibility path was introduced.
Preparation guards are process-level observations, not proof of OS isolation.

Evidence strength: raw identity, full-file preparation, seven-file repeat equality,
raw-backed selected-text verification and regression checks passed; overall
completion confidence C because the cumulative acquisition budget remains unproven.
No source changes, reacquisition or new data preparation followed the finding.
No failed identity, schema or reproducibility check was observed. No calibrated
sample or scoring validity is claimed. Next action belongs to independent review.

This bounded manual work record does not initialize an Aegis project workspace.
No workspace bundle/check helper or extra governance baseline was introduced.
