# Litmus — portfolio presentation

## Short project description

Litmus is a local evidence workbench for text-origin signals, writing-pattern
observations and image Content Credentials. It explains why a result was produced
and preserves the original report for inspection. It does not prove authorship
or assign a probability that a person used AI.

## Engineering story

The central challenge was making uncertain signals inspectable without presenting
them as certainty. Litmus separates model scores, writing observations and signed
provenance, rather than merging them into a misleading AI percentage.

A Python report assembler serves both CLI and browser workflows. The local browser
uses plain JavaScript and a standard-library loopback server. Bounded workers,
request deadlines and durable status references keep failures understandable;
request timeout never falsely implies native work was cancelled.

Scientific reproducibility is a first-class constraint. Source-group separation,
exact configuration identities, strict threshold ties, saved score ledgers and
grouped intervals support a read-only verifier. The accepted evaluation is frozen;
future dependency or model changes cannot silently inherit its calibration.

## Results to discuss honestly

On the frozen held-out source-group subset of RAID train.csv, clean-text AUROC
was 0.80358, TPR 66.37%, and observed FPR 4.59%. Homoglyph attacks reduced detection
to 8.59%. These are sample-specific results, not universal accuracy. See README
for intervals and denominators. Weaknesses are part of the result, not hidden.

The UI readiness run passed 883 default tests with 21 slow tests excluded, plus
browser and wheel checks. The subsequent dependency advisory audit found matches
in four installed packages; the release remains a private draft pending security
triage. No claim of production internet-service readiness is made.

## Five-minute demonstration

1. Explain the separation between origin, writing observations and provenance.
2. Launch Start-Litmus.cmd and open the loopback address. All checks start off.
3. Upload tests/fixtures/inputs/quality.txt and enable content observations only.
   Explain that matching wording is not evidence of AI authorship.
4. Show reasons, expanded caveats, original evidence and downloaded JSON.
5. Use tests/fixtures/c2pa/active_ai_declared.jpg with C2PA enabled. Explain
   constructed provenance, unknown signer trust and the empty production anchors.
6. Show the architecture, evaluation limitations and read-only verification record.
   Do not improvise live detector claims on an incompatible machine.

## Ownership and assistance

Ryan owns scope, approvals and the recorded project decisions. Codex assisted
implementation/testing; Claude supplied independent code-review feedback.
Present the design decisions and evidence you understand, and identify areas you
are still learning. Do not claim sole manual authorship, production adoption,
human review that did not occur or validation on machines that were not tested.

## Interview discussion prompts

- Why separate provenance from statistical origin signals?
- Why does a threshold require exact configuration matching?
- What did the homoglyph result reveal about robustness?
- Why does timeout not cancel native work, and how does the UI communicate it?
- How should dependency security updates coexist with immutable research evidence?
- What would need to change before multi-user/public deployment?

The strongest next milestone is resolving advisory exposure without invalidating
historical science, followed by independent accessibility and installation checks.
