# R1-D3 implementation prompt — APPROVED

**Status: APPROVED by Ryan on 2026-10-30 in the continuation instruction.**
The complete proposed prompt below is retained as the approved scope.
Approval permits D3 only, followed by a commit and independent review.

Installed-wheel clarification from Ryan: use the existing pinned runtime
dependencies without downloads or new dependencies, and assert that Litmus
imports from the newly installed wheel rather than the editable checkout.
The check uses the existing `.venv` interpreter in isolated mode (`-I`) with
its runtime site-packages available and a fresh wheel `--target` installation
first on `sys.path`; every loaded Litmus module must resolve inside that target.

Continue Litmus R1-D3 in C:\Users\Ryano\Projects\litmus.

Authorization: D3 only, after Ryan approves this prompt. Preserve all existing
uncommitted and untracked work. Use the existing .venv and pinned dependencies.

First read repository instructions, git status/log, docs/decisions.md,
docs/plans/R1-D-PLAN.md including corrections, docs/interfaces.md, the D1/D2
evidence, and the report/CLI/schema/ingestion code. Expected starting HEAD:
0c6fa08edeb856633e86a65667461c73b1708bca. Inspect any differences before proceeding.

## Accepted baseline and documentation reconciliation

Record D2 closure as reviewer-reported: Codex independently reviewed 0c6fa08;
628 default tests, Ruff and pip check passed; both remote-reference trap/control
variants and bounded-worker tests passed; the repository was clean. Do not
present these as fresh builder-run results.

Reconcile stale current-status and plan statements with reviewed D1/D2 evidence,
while preserving historical entries and keeping decisions.md append-only:

- D1 and D2 are closed; D3 is authorized only by approval of this prompt.
- D2 already implements mapping, ten ordered rules, declaration detection,
  context attribution, the remote adapter and the bounded worker.
- The working configuration route is Settings.from_dict plus Context, not
  Settings.set for trust. Settings acceptance alone does not prove effect.
- The production trust resource is the packaged, empty, versioned PEM file,
  not the originally proposed JSON file.
- The captured manifest/results structure and ingredient active_manifest link
  are demonstrated by D1 captures. Overall validation_state is diagnostic.
- The reviewed mapping has 45 codes: nine observed in real captures and
  36 demonstrated only through constructed injection. Preserve this distinction.
- Ingredient binding matches cannot validate the analyzed asset; attributed
  negative codes can mark an ingredient invalid. Unreferenced manifests do
  not trigger the ingredient declaration rule.
- The generic remote-error adapter uses the exact reviewed prefix, pinned
  c2pa-python 0.38.0 / SDK 0.91.0, and explicitly disabled fetch.
- Production signer_trust remains unknown regardless of SDK trust diagnostics.
  Do not infer anything broader about SDK built-in anchors.

Attribute the previously supplied C2PA 2.5 §14.8, “Validate the time stamp,”
citation to the reviewer:
https://spec.c2pa.org/specifications/specifications/2.5/specs/C2PA_Specification.html#_validate_the_time_stamp

State that the reviewer supplied this citation; the builder did not independently
fetch or verify the specification text. Correct the inherited attribution to
Ryan/the builder in current documentation and constructed-fixture descriptions,
without rewriting historical decision entries or old verification records.
Timestamp evidence remains explicitly constructed. No real TSA validation was
demonstrated, and insideValidity alone does not establish verified signing time.

## 1. Opt-in activation and report placement

Implement --c2pa {off,on}, default off.

Omitted and explicit off must produce identical report bytes and retain existing
golden reports unchanged. Off must not initialize the C2PA analyzer, import the
native SDK unnecessarily, or start its worker.

With on, run C2PA only for accepted JPEG/PNG/WebP image segments, using already
ingested bytes and MIME type. Do not reopen the input path or bypass ingestion
limits. Replace the image-origin placeholder with C2PA OriginEvidence.

Text segments receive no C2PA evidence or unsigned-image metadata. Preserve text
origin evidence, scoring configuration/hash and quality behavior. A text-only
request must not initialize the C2PA SDK or worker.

Retain an explicit activation prerequisite backed by the reviewed D1/D2 offline
evidence. Test refusal when that prerequisite is unavailable; do not run tests
or fetch anything dynamically to establish it during analysis.

Reuse D2's policy, mapping, rules and worker. Do not change their semantics as
part of integration unless a demonstrated integration defect requires a scoped
fix and regression test.

## 2. Evidence contract

Use method_id="c2pa_provenance" with a documented method_version.
raw_score, score_direction and calibration must be null.

Populate provenance with:

- manifest_present: embedded, remote_reference_only or none when established;
  use an explicit unavailable/null value for errors that leave presence unknown;
- active record and referenced ingredient records, preserving identity,
  relationship/title, integrity, signature, timestamp, signing_time_basis,
  signer_trust, declared_ai_use, sources and notes;
- mapping_version;
- production trust-list name, version, SHA-256 and anchor count;
- c2pa-python and native SDK versions;
- applied offline/trust settings and production policy identity.

Populate details with:

- diagnostic validation_state;
- raw status entries with list, manifest attribution, assertion URL and origin;
- unmapped and unattributed entries;
- selected rule and available read/response timings, with units and meaning.

Preserve the rule label and specific error reasons, including settings rejection,
mapping/read failures, c2pa_timeout and c2pa_worker_busy. Serialize plain JSON data;
do not leak SDK objects, streams, exceptions or dataclass internals.

For unavailable information, report null/empty data with an explanation.
Do not fabricate validation states, successful settings application or timings.

Production trust must always remain unknown; no production result may be
supports_ai. Keep trusted-outcome tests behind the existing explicit test-only
policy and anchor configuration.

## 3. Limitations and failure behavior

Include the empty-production-trust limitation in every C2PA evidence record and
in reports where C2PA ran. Explain that valid active AI declarations therefore
yield inconclusive / untrusted_signed_ai_declaration.

Include the applicable limitations:

- provenance metadata does not detect AI-generated image content;
- absence of credentials or declarations is not evidence of human origin;
- remote manifests are not fetched;
- SDK trust observations are separate from Litmus policy;
- timestamp evidence demonstrated by this project is constructed;
- timeout is a response deadline, not native cancellation.

Preserve one worker, one outstanding task, immediate busy responses and recovery
on the same worker. Resources remain worker-owned until native work finishes.
Do not replace the worker, queue additional jobs or report cancellation.

Read/settings/mapping/timeout/busy failures must produce valid error evidence
without losing the report. Define and test CLI exit behavior: a successfully
emitted report may contain analyzer error evidence; activation or initialization
failures that prevent a valid report must fail clearly. Never silently fall back
to the disabled placeholder after accepting an image analysis request with on.

Adjust report-level placeholder wording only where C2PA actually ran, so an
enabled report does not falsely claim “no C2PA analysis.” Preserve default bytes.

## 4. Minimal unsigned metadata

When C2PA is enabled for an accepted image, add unsigned_metadata under the C2PA
provenance record, separately from signed assertions.

Use Pillow and in-memory ingested bytes:

- EXIF tag count;
- Software, Make, Model and DateTime when present, each converted to text and
  truncated to 256 code points;
- XMP presence and byte length where Pillow exposes it.

Do not parse XMP, enumerate arbitrary metadata, or add dependencies.
Label the summary “unverifiable; editable; not evidence.”
Distinguish unavailable/not examined from confirmed absence.

Metadata extraction failures must be isolated and documented. The summary,
including suggestive strings such as “AI generated,” must never affect result,
reasons, signed declaration detection, trust or validation fields. Do not
interpret EXIF DateTime as verified signing time.

## 5. Verification

Add meaningful tests for:

- omitted versus off byte equality and unchanged default golden reports;
- enabled JPEG/PNG/WebP evidence, no credentials, remote-only, tampered,
  active declaration and ingredient-only declaration;
- unchanged text-origin evidence and quality behavior, using model-free stubs
  where appropriate;
- report/evidence round-trip through existing serialization/deserialization;
- complete fields, unavailable values, reasons and limitations on error paths;
- unsigned-metadata presence, truncation, failure isolation and result invariance;
- CLI help, accepted/rejected option values, stdout/-o behavior, activation
  refusal and documented exit codes;
- fresh-process import isolation: no SDK/worker for off or text-only input,
  and no torch/transformers/scorer imports for the image C2PA path;
- report-level timeout/busy/recovery behavior with short injected deadlines;
- both remote-reference variants through the enabled integration path, with
  zero-connection assertions and passing paired positive controls.

Build and install a wheel into a temporary location using existing build tools,
--no-deps and --no-build-isolation, without downloads or new dependencies.
From outside the repository, verify imports actually resolve to the installed
artifact, packaged trust-resource bytes/hash and emptiness match, enabled image
analysis works, and test anchors/private keys are not packaged. Do not allow the
editable checkout to mask a packaging failure.

Run the full model-free suite from inside and outside the repository, Ruff,
pip check, git diff --check, and the applicable non-ASCII audit. Run additional
checks only where changes justify them. Report exact commands, results,
limitations and anything not run. Do not claim network isolation: the trap
tests establish observations only for the exercised fixtures/configuration.

## 6. Documentation and delivery

Update README, interfaces, the D-plan's current statements, and append decisions.
Replace stale README status claims with the actual supported behavior and limits.
Document activation, schema, unsigned metadata, trust policy, error/exit behavior,
reviewer citation attribution and constructed evidence.

Preserve earlier evidence records; append corrections rather than relabeling
past builder results as independently verified.

Commit completed D3 work and actual evidence, report commit hashes, changed
files, exact check results and git status, then stop for independent review.

No RAID acquisition, calibration, image detector, UI work, new dependencies,
third-party fixtures, destructive cleanup or history rewriting. Do not enable
C2PA by default or expand beyond D3.
