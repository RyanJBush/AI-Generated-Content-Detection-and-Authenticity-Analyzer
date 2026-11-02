# R1 professional-readiness improvement — 2026-11-02

Authority: Ryan's supplied professional engineering/UX/recruiter audit prompt.
Baseline 0afbb5a. Branch codex/recruiter-readiness. Codex running GPT-6 Astra
owns implementation and integration; Claude Code is a separate read-only reviewer.
No separate third model implementation session is claimed. No frozen E/F/G
source, scientific data, score, threshold, lexicon, or original receipt edits.
No new dependencies, detector tuning, held-out access, R2–R4 work or public hosting.

## Findings and acceptance

| ID / priority | Evidence and location | Remedy / effort | Acceptance and verification |
|---|---|---|---|
| UX1 / P1 | Actual baseline browser: disabled text check says Inconclusive and R0 skeleton. static/app.js render | Present Not run; translate known reasons; preserve raw JSON. Small | Off stays off; disabled check clearly identified; exported report unchanged; browser cases |
| UX2 / P1 | app.js polling catch releases all controls and loses job ID; no recovery/refresh handling | Remember only job ID/options in tab session; explicit status retry, bounded requests, no resubmission. Medium | Poll failure/reload recovers original job; only one POST; no raw text/file/token storage; browser fault injection |
| HTTP1 / P2 | server.py read(length) uses per-read timeout; trickle can occupy single server | Absolute upload deadline and bounded chunks. Small | Real trickle test rejected within deadline, no analysis; valid upload still works |
| HTTP2 / P2 | OpenAPI 500 JSON documented; handler can drop unexpected exception | Catch unhandled request failures before response begins. Small | Injected exception returns generic JSON500 without internal text; server recovers |
| HTTP3 / P2 | filename allows bidi/format/C1 characters | Reject Unicode Cc/Cf display controls. Small | Tests reject unsafe names; ordinary Unicode names still accepted |
| DOC1 / P2 | README opens with milestone/status rather than concise technical value; no architecture diagram/screenshots at entry | Add product summary, actual screenshots, architecture, developer tests and honest AI contribution note. Medium | Links/files/commands checked; no invented users, contributions or new metrics |
| A11Y1 / P2 | Small 11/12px explanations; no skip link; responsive layout exists | Retain navy/teal/neutral identity, reusable size/radius tokens, clear focus and readable supporting text. Small | Keyboard flow, mobile/desktop and 200% reflow; contrast calculations; screen-reader certification not claimed |

No P0 confirmed. Native isolation, dependency vulnerabilities, alternate hardware,
and full screen-reader operation are unverified risks, not established defects.
Local temporary cleanup failure remains explicitly documented. Privacy review
still required before changing GitHub visibility. Existing ML limitations remain.

## Collaboration prompts (copy-ready)

### Claude independent review

Review Litmus at C:\Users\Ryano\Projects\litmus on codex/recruiter-readiness,
baseline 0afbb5a. Read-only, no edits, tests, network, raw dataset/model access or
subagents. Inspect SPEC.md, README.md, INSTALL.md, docs/interfaces.md, this plan,
local_ui code/assets, tests/test_local_ui.py, and new audit evidence. Evaluate
architecture ownership, safe offline boundaries, accessible UI states/recovery,
scientific claim accuracy and recruiter credibility. Verify changes preserve
default reports and all frozen E/F/G paths. Findings first: severity, file/line,
evidence, remedy, acceptance. Separate defects, hypotheses and missing evidence.
Do not claim executable tests. Give advisory release readiness and residual risk.

### Codex implementation and verification

Work only on codex/recruiter-readiness, one writer. Implement UX1/UX2/HTTP1–3/
DOC1/A11Y1 above; preserve current report/scorer owners and exact exported JSON.
Read docs/api/local-ui.openapi.json before API changes; retain endpoint/schema
compatibility. Add meaningful regression tests, exercise browser happy/error/
busy/reload/retry/empty/unsupported states and mobile/keyboard/reflow. Run Ruff,
pip check, selected model-free tests inside/outside, fresh installed-wheel and
read-only frozen-science verifier. Do not run held-out scoring, recalibration,
dependency downloads or new benchmarks. Record exact commands/results and
Verified Passed/Failed/Not Tested/Not Applicable release gates. Address Claude
findings, commit only task-owned changes and retain unresolved limitations.

## Progress

- Completed: UX1/UX2/HTTP1–3/DOC1/A11Y1 implementation; regression tests;
  17 browser scenarios and 6 recovery/native scenarios; desktop/mobile inspection;
  installed wheel; synthetic CUDA/native checks; frozen scientific verification;
  two actual read-only Claude reviews and disposition of findings.
- Current: delivery of the reviewed implementation and verification evidence.
- Remaining: optional full screen-reader, alternate-browser/hardware and dependency
  advisory audits. Public hosting is outside scope, not a release deliverable.
- Blocked: none for the local, private portfolio showcase.

## Review disposition and release gate

Claude's initial F1–F3 were fixed: dismiss unavailable job tracking without
claiming cancellation, sanitized phase/class diagnostics, and visible quality
caveats. F4/F5/F7–F13 were addressed through reason mapping, uncertain-submission
copy, local-file upload guidance, contract/privacy/focus corrections, stronger
HTTP assertions and clearing stale storage before rendering. F6 slow-header
occupation remains an explicitly documented limitation of the local-only server.
The final review found no blocking code defects; its outstanding evidence tasks
are fulfilled by the records linked below. Claude reviewed source; executable
verification is attributed to Codex, not Claude.

[Verification and exact commands](../../eval/results/readiness/VERIFICATION.md)
contains gate classifications and reproduction notes.
[Machine-readable identity record](../../eval/results/readiness/verification.json)
binds the tested implementation and evidence bytes without a self-hash cycle.
[Initial Claude review](../../eval/results/readiness/claude-review.md) and
[follow-up](../../eval/results/readiness/claude-final-review.md) retain actual
review text, including observations made before the final evidence was saved.

Scientific assessment: no formulas, model/configuration identities, thresholds,
selection, split or scientific artifacts changed. Saved evaluation reassembly
and accepted historical source reconciliation pass. The development-selected
5% target does not guarantee population FPR; 1% calibration remains disabled.
No new baseline experiments or general accuracy claims are introduced.
