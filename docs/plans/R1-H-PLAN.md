# R1 completion: approved execution plan

Ryan approved finishing the current R1 on 2026-11-02: independent G review,
local interface and final usability/packaging checks, no new dependencies or
scoring/calibration changes. Baseline clean 5c0adcf. Governing R1-PLAN/corrections,
SPEC 7/11, interfaces, frozen F/E and completed G evidence remain authoritative.
No repository AGENTS.md/CLAUDE.md found. Approval proceeds through execution;
this is not another approval request. R2–R4 remain outside scope.

New code is necessary for the missing file-to-report browser workflow. Preserve
the existing report assembler and analyzers as the sole analysis owners. New
local_ui package/server/assets and module launcher sit outside every frozen
F/E/G source path. Existing CLI/default reports, hashes/calibration/evidence
remain unchanged. UI imports no evaluation, acquisition or calibration drivers.
No parallel analysis path, threshold or detector math is introduced.

Use stdlib HTTPServer on 127.0.0.1 only, one bounded background analysis worker,
in-memory last job/report, temporary uploads removed by their owner. No accounts,
cloud, persistence, remote assets or network installation. Three explicit
options (text origin, quality, image provenance), all initially off. CUDA only
when text origin is enabled; absence/profile mismatch is displayed honestly by
existing production logic. No real model scoring in completion verification;
mock/synthetic UI checks suffice and preserve the held-out dataset.

The client uses a labeled file control, clear options, analyze/progress/recovery,
separate origin/quality panels, reasons/limitations, raw score labeled not a
probability, complete JSON export. Escape content using textContent, keyboard
controls/live status and responsive layout. No automatic retry/cancellation of
native work. Busy submissions rejected; closing a tab does not cancel analysis.
Protect local service with exact Host/Origin checks, per-session secret header,
bounded body/filename/options, request timeout and no arbitrary filesystem route.

Written transport contract: docs/api/local-ui.openapi.json, independently
reviewed before endpoints. Source count/worker/cleanup tests and real loopback
HTTP contract tests precede implementation. TDD route auto/strict: behavior,
local permission boundary and asynchronous state justify constructed tests first.
No new validator dependency: stdlib schema subset assertions in contract tests.

G review found missing intent/access validation before legacy resume (actual
uninterrupted results unaffected), and timing-bearing receipt rerun defect.
Disposition: retain all original code/evidence bytes as historical provenance;
retire legacy G scoring/recovery/receipt creation from supported commands. New
release_verify.py + scripts/verify_r1_release.py validate every event against
immutable metadata before historical full verification/reassembly, check accepted
Git blobs/digests, reject corruption/incomplete data, print deterministic read-only
results and never open test blobs/models. No unqualified claim that historical
recovery requirements passed. Reviewer will inspect additive verifier/disposition.

Tasks: (1) independent G/contract reviews, (2) strict supported verifier/tests,
(3) isolated UI/server/assets/launcher/tests, (4) actual browser walkthrough at
desktop/mobile, unsupported input, error/busy and export; fake scorer/model-free,
(5) wheel with existing pinned dependencies/no downloads, assert wheel imports,
selected model-free tests inside/outside, Ruff/pip/whitespace, frozen-byte proofs,
(6) fresh independent final review/fixes, honest README/interfaces/decisions,
commit evidence and tested R1 delivery. No history rewriting or raw data in Git.

Stop if completing UI requires frozen-source edits, any scientific identity
mismatch, extra dependency/download, rescoring/recalibration or wider release.
Native isolation/hardware portability and full accessibility audit not claimed.

## Execution (2026-11-02)

All tasks executed. Fresh independent scientific, contract and UI reviews pass
with the explicit historical recovery retirement. No unqualified old G0–G5
compliance claim. Strict supported verification is repeatable and read-only;
old scientific artifacts/receipts/sources stay unchanged. UI review fixes covered
by actual browser and method regressions. Final selected suite632 pass/21 slow
excluded inside19.31s/outside17.40s, focused45 pass1.62s; Ruff,pip,wheel,launcher,
browser desktop/mobile and source/byte checks pass. Actual production app runs
on127.0.0.1:8765. Evidence/digests and omissions: eval/results/r1h/verification.json.
R1 local completion, not authorization for future modalities/public deployment.
