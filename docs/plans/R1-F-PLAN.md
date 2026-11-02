# R1-F implementation plan — development calibration and committed freeze

**APPROVED by Ryan, 2026-11-01, at 3f3e787: F0–F5 including local CUDA synthetic
checks and development-only scoring.** The implementation must be committed
before scoring. Subsequent artifact/evidence/freeze work may not change hashed
implementation sources and retain scores under the old identity. Explicit
clarification: one-way binding only; the freeze records the calibration artifact
digest, and the artifact never records a freeze digest. No R1-G authorization.
The proposal text below is retained as the approved procedure; execution results
are recorded separately. Historical transfer compliance remains unproven.

## 1. Goal, authority and boundary

After explicit implementation approval, score the existing development rows on
the approved production CUDA profile, create only a valid 5% calibration, and
commit an independently reviewable freeze before any R1-G test scoring.

Authority, in precedence order: Ryan's explicit approvals/corrections;
R1-PLAN-CORRECTIONS-A.md (especially CA2); approved R1-PLAN.md sections 1.1–1.2
and checkpoint F/G; SPEC Addendum B5 as resolved by that plan; SPEC sections
10.1, 10.4 and 10.9; current docs/interfaces.md and reviewed B1/B2/E evidence.
The old documents' draft/OPEN/authorization lines describe their original dates;
later approvals and checkpoint closure are recorded in docs/decisions.md.
The older Addendum A4 environment-only proposal does not override strict
execution-profile hashing and CA2. No upstream research or network is needed.

Planning baseline: clean master at
`d50b7e0c5cb329b7e12cf2fcba54c45aa50e41c7`. No repository AGENTS.md found.
Ryan supplied independent review of that correction: 68 offline RAID tests,
Ruff, pip check and whitespace checks passed; all 26 historical evidence files
are preserved; reconciliation validates both runs and scientific files match.
**R1-E is closed on that reviewer-reported evidence, with its existing narrowly
scoped exception. Historical cumulative transfer compliance remains unproven.**
Acceptance of that uncertainty is never proof the original transfer met 13 GB.
The historical receipts/failure audit/source maps remain unchanged.

Only development data may be scored in F. No test blob is opened, no test score
is created, loaded, inspected or used for any decision. Reading committed test
metadata solely for whole-manifest identity is distinct from accessing texts or
scores. No G evaluation/metrics/bootstrap, network requests (including loopback
controls), reacquisition, reselection, seed changes, refill, CPU calibration,
model/formula tuning, 1% calibration, UI or new dependencies. C2PA and quality
behavior remain separate; quality results never affect origin decisions.

## 2. Existing owners and minimum implementation boundary

Existing scorer owners: scorer/loader.py owns local loading/numerical settings;
scorer/identity.py owns configuration hashes; scorer/analyzer.py owns production
scoring/evidence; scorer/calibration.py currently returns the first matching JSON
without full validation and does not apply thresholds. schemas.Calibration is
the public report projection, not a sufficient artifact validator. These gaps
require code for creation, validation, application and freeze enforcement.

Proposed files (not implemented by this plan):

| Owner/file | Smallest necessary change |
|---|---|
| src/litmus/scorer/calibration.py | Pure orientation/threshold selection, artifact validation, exact matching, calibrated decision and freeze validation |
| src/litmus/scorer/analyzer.py | Apply only validated matching calibration; emit existing report Calibration projection and explicit reasons/limitations |
| src/litmus/scorer/identity.py | Bind all decision/calibration implementation sources in the fixed source list |
| src/litmus/calibration_run.py (new) | Dev-only manifest input, scorer session, durable row journal, count reconciliation, artifact/freeze assembly |
| scripts/calibrate_r1f.py (new) | Explicit local dev-run/verification commands; no test split option or generic evaluation runner |
| tests/test_calibration.py and tests/test_calibration_run.py (new) | Statistical, schema, isolation, interruption, freeze and consumer tests |
| tests/test_scoring_identity.py, tests/test_cli_golden.py, tests/test_schemas.py | Exact-match/application/report regressions at existing seams |
| docs/interfaces.md, README.md, docs/decisions.md; new F metadata/results and calibrations/*.json | Actual contract/results/limitations and committed freeze, only after verification |

Use existing .venv, pinned torch/transformers/tokenizers, stdlib JSON/hash/CSV-free
blob access; no new dependency. Runner remains outside data_prep/: do not change
E selection, pipeline, config.py or scorer/tokenize.py, or broaden E's reconciliation
allowlist. Scorer math/formula/preprocessing remain unchanged. Calibration gets
its own schema/procedure version; do not change config.py merely to label it.
If implementation needs a preparation-hashed file changed, stop for a new
explicit reconciliation decision instead of silently editing E evidence.

Propose adding scorer/calibration.py and litmus/calibration_run.py to the seven
existing scorer identity SOURCE_FILES (nine exact paths, sorted). Existing
analyzer.py/identity.py changes also change the scoring hash. Preserve the
CRLF-to-LF source normalization rule and hash the list itself. Data artifacts
must not enter this source hash: artifact creation cannot change its own scorer
identity. Freeze separately binds the runner/script and validation sources.
No duplicate statistical implementation in the script or runtime analyzer.

TDD route for the proposed build: auto/strict for this behavioral/persistence
boundary, using synthetic scores/fake scorers before real dev scoring. Current
turn is documentation only. Execute inline after approval; no delegation needed.
Retire the placeholder calibration_application_not_implemented path when the
validated implementation replaces it; retain CPU/no-match/incomplete-profile
inconclusive behavior. No second permissive legacy artifact loader.

## 3. Prepared identity and dev-only input contract

Use the retained primary manifest, not raw train.csv, a new selection or a
convenient directory glob. Preserve these reviewed anchors:

- Scientific manifest payload SHA-256:
  `8f0a36e95e9745e27bd444b94fe96381c5c0cd98744b2abd52bd2a6ce579c5d9`.
- Dev projection SHA-256:
  `57bbfc53c6fc9bf482367d18aec29a1e991792fad75d9885e2ad4630ee467453`.
- Explicit E source reconciliation: eval/results/r1e_budget_fix_source_reconciliation.json,
  byte SHA-256 `836baccb57a834bca3c3fcd9e28862c1dbcf99879f6a22b008d3afc867d5a851`.
- Corrected existing-data verification: eval/results/r1e_budget_fix_source_verification.json;
  historic generation commit b2d24da, corrected verifier commit d50b7e0.

Validate envelope self-digest, ledger hashes, split digest/counts/invariants and
explicit verify_source_version reconciliation. Default source mismatch rejection
stays active. Never replace historical generation hashes with current F source
hashes or silently skip source checks. Unchanged E modules keep the reviewed
reconciliation valid; the F scorer identity is a separate identity domain.

The existing split digest is SHA-256 of the concatenation of canonical retained
row JSON plus LF for split=dev, preserving retained-ledger order (manifest.py).
Create an immutable F dev-input projection using exactly those bytes and verify
its digest equals the existing dev digest. Load only its listed dev blobs from
data/raid/prepared/primary/texts/, with resolved-path containment checks. Verify
exact raw UTF-8 byte hash before strict decoding without newline/Unicode rewriting;
retokenize locally and match E's window hash, token counts and character range.
Stop on any identity/window discrepancy; do not call it a score exclusion.

Metadata observed during planning, not scoring: **1,484 dev rows**, comprising
298 clean humans, 298 clean machines, 298 homoglyph, 292 paraphrase and 298
zero_width_space. These are expectations to verify at run start, not a claim
that all rows will produce valid scores. Test rows are absent from the runner's
input view. Reject injected test IDs/splits, unknown/duplicate IDs and any blob
outside the projection. Tests spy on file access and scorer calls to prove this.
No full E re-preparation or real selection reconstruction is needed for F.

## 4. Production profile preflight and exact scoring identity

Finish and verify all source changes before the first real dev score. Commit
the scoring/validation implementation first, then run in a fresh process from
that fixed source revision; record a clean source tree and exact hashes. Any
subsequent hashed source change invalidates that scoring session. Freeze creation
is a later data/evidence commit; it cannot modify scorer code after scoring.

Use production load_pair(device='cuda') and BinocularsAnalyzer.score_text with
one reused loaded pair, not a second evaluator formula. Apply numerical settings
before CUDA/cuBLAS initializes, offline before HF imports, local_files_only=True,
batch 1, eager attention, fp32 weights and reductions, TF32 off, precision highest,
deterministic algorithms true, CUBLAS_WORKSPACE_CONFIG=:4096:8. Require the
approved RTX 4060 Laptop GPU policy, both models on CUDA in eval/inference mode,
matching output dimensions, pinned tokenizer/model revisions and local asset
identities. Missing local assets stop; no download or CPU fallback.
Use the committed models.manifest.json to verify model/config/tokenizer file
sizes and hashes without invoking download_models.py or changing that manifest;
record its digest with the preflight. Use r1a_tokenizer_checks.json for the
existing tokenizer compatibility evidence, not as a replacement for local checks.

Require profile_failures(profile, models=...) == {} and initialization-order
evidence false for cuda_initialized_before_settings. Read profile from actual
loaded models/runtime, not requested values. Missing/unknown/unavailable driver
or any required metadata stops with execution_profile_incomplete (CA2). Re-read
effective settings before every score through the production path and recheck the
full session profile at resume/end. A drift or hash change aborts the session;
never merge profiles, reapply settings to conceal drift or reuse a CPU hash.

Use identity.config_fields/static_fields/source_sha256/scoring_config_hash,
not a runner-specific hash. Persist the complete canonical configuration and
its exact SHA-256. Canonical JSON is UTF-8, sorted keys, compact separators,
ensure_ascii=False; additionally reject non-finite values before hashing.
The exact field set remains the existing identity contract:

- Static: scorer_version, formula_id, observer_repo/commit, performer_repo/commit,
  tokenizer_json_sha256, add_special_tokens, split_special_tokens, truncation_side,
  max_tokens, min_tokens, weight_dtype, reduction_dtype, score_direction,
  preprocessing_version.
- Profile: device_type, gpu_name, nvidia_driver_version, cuda_runtime,
  torch_version, transformers_version, tokenizers_version, attn_implementation,
  batch_size, matmul_allow_tf32, cudnn_allow_tf32, float32_matmul_precision,
  deterministic_algorithms, cublas_workspace_config, weight_dtype,
  reduction_dtype, os_family, cuda_initialized_before_settings. Duplicate dtype
  fields agree with the static values; fields are merged once, never omitted.
- Source: exact source_files list and normalized source_sha256 aggregate.

**The final F scoring_config_hash is UNKNOWN until approved implementation and
fresh runtime preflight.** The old B2 hash
eb2db0e9d79c6d4e4b119a4466e901ee5264344e0ed516ea0777cc4222d0ab97
is historical evidence only, not an approved hash to copy into F. Source/profile
changes require a new calibration; no tolerance/probe-based compatibility alias.

## 5. Scoring validity, failures and count gate

Score all 1,484 approved dev rows in deterministic retained order, one production
call per row, with calibration lookup disabled for creation so an old artifact
cannot affect validity. Persist raw score/statistics, actual scoring_config_hash,
complete-profile status, input/window hashes and counts, row/source ID, split,
role/attack, reasons and status; no raw text/logits/token arrays in Git.

Valid score requires finite numeric non-bool raw_score and statistics,
nll_performer >= 0, xent > 0, production validate_statistics success, matching ratio/window/counts,
64..512 scored tokens with n_input_tokens=T and n_target_tokens=T-1, exact
session hash/profile and no scoring error. The uncalibrated creation-time
inconclusive result with a valid raw score is not itself a numerical failure.
Missing scores, non-finite values, wrong windows, stale hashes and changed
profiles cannot enter calibration as zero, imputed, clipped or rounded values.

Identity/schema/profile drift, CUDA failure/OOM or systemic integrity failure
stops the run without publication; no automatic CPU/batch/precision change.
Document per-row numerical/validation failures as terminal failed rows with
fixed reason codes. Do not repeatedly retry until a favorable valid score appears.
After interruption, incomplete attempts may be recomputed as described below;
that is distinct from replacing a terminal failed result.

Negatives = **valid clean human dev rows only**, one source/row per E group.
Clean machine and attacked scores never choose c. A machine/attack score failure
does not remove its otherwise valid human negative or trigger new pair cleanup:
that would condition the negative sample on positive behavior. Record affected
pair availability and per-role failure counts separately. E input selection,
exclusions and IDs remain fixed. No threshold-based row exclusions.

Compute actual N from the final validated score ledger, reconciling all attempted,
valid and failed dev humans (expected inputs 298). Require **N >= 200** after
score validity exclusions. If N < 200, create no calibration/freeze authorizing
G; save counts/reasons and stop for review. Do not refill, alter seed, borrow test
rows, lower the minimum or assume E's 298 humans equal 298 valid scores.
All dev rows need a terminal ledger status before calibration publication.

## 6. Exact 5% threshold and application

Follow SPEC 10.4 literally; no quantile interpolation, threshold search on
positives, epsilon comparisons, random tie breaking or probability conversion.

1. Declare score_direction=lower_means_more_machine; orient r=-raw_score.
   The generic pure helper may also support the declared higher direction as
   identity for synthetic tests, rejecting any unknown direction.
2. Candidates are distinct observed finite r values of the N valid dev humans.
3. For each candidate c in ascending order, count k = number of negatives with
   r > c, strictly. Choose the first/smallest c with **20*k <= N** (exact alpha
   1/20, avoiding floating rounding in the empirical count test).
4. Flag iff r > c. Equality never flags; for this lower-direction scorer the
   equivalent raw-score condition is raw_score < -c. Store c in r-space and
   label the transform/strict comparison explicitly to avoid sign ambiguity.

At N=298, k may be at most 14, not 15; actual N may differ. Synthetic examples:
N=200 distinct r=0..199 gives c=189 and k=10; N=298 distinct r=0..297 gives
c=283 and k=14; all identical negatives select that value and flag none.
Threshold ties may make achieved empirical dev FPR lower than 5%. Record N, c,
k and k/N, threshold-equality count and failed-negative counts. This is an
empirical dev operating point, not a guarantee of population/test FPR.

**1% calibration is disabled in R1**, regardless of helper capability or N.
No 1% file/threshold or claim is produced. A valid matching calibration yields
supports_ai only for strict passage, otherwise no_signal, never human-made.
CPU, invalid/incomplete profile, missing/invalid calibration or mismatched hash
remains inconclusive with explicit reasons; numerical errors remain errors.
Raw scores are not probabilities and calibrated evidence is not a verdict.

## 7. Calibration artifact, validation and compatibility

Proposed artifact: calibrations/r1f_<scoring_config_hash>_alpha005.json, schema
version r1f-calibration-v1. Bind full scoring_config and exact hash, procedure
ID/alpha=0.05 (also integer ratio 1/20), direction/transform/comparison='>', c,
actual N (n_dev_negatives), k, tie count, dev input digest/dev_set_id, accepted E
manifest digest/reconciliation digest, validated dev-score ledger digest,
source-run ID and creation metadata. Time/path telemetry is outside scientific
identity. Compute artifact digest with a documented nonrecursive canonical
envelope, rejecting NaN/Infinity and ambiguous duplicate JSON keys.

Creation/verification must rederive c and counts from the bound negative ledger,
checking c is an observed candidate, satisfies the count constraint and is minimal.
Runtime loader validates schema/types, finite values (bool is not numeric),
SHA-256 formats, N>=200, k/tie bounds, exact 5% policy, declared direction,
canonical self-digest/config hash and consistent embedded profile. The published
artifact links the independently verified creation/freeze evidence; ordinary
analysis does not need raw development texts or retokenize them to use it.
Malformed/unreadable/unsupported or ambiguous duplicate matching artifacts fail
closed, with actionable diagnostics; do not select the first matching JSON.
Different valid hashes mean no calibration, never nearest-match reuse.

Use schemas.Calibration for the existing report projection (hash, dev_set_id,
alpha, threshold_c, n_dev_negatives, created); put procedure/direction/count/
artifact identity details in the existing details object. JSON report round-trip
must preserve c and N without loss. No expansion of generic result vocabulary.
Use the existing calibration-directory contract and explicit directory injection
for tests; package/deployment redesign is out of scope. Do not claim installed
GPU calibration portability; exact source/runtime identities must be established
in any later deployment before the artifact can match there.

## 8. Durable journal, reproducibility and interruption recovery

Proposed script operations: preflight, score-dev, verify-dev, freeze; explicit
local input/run/output arguments only. No --split test, implicit test discovery,
overwrite/rescore-all switch or G runner. Enforce one writer with exclusive lock
and exclusive run/artifact creation. A stale lock is reported, not silently
deleted. Handle release normally; preserve partials for inspected recovery.

Write an immutable run header binding input/source/profile/scoring hash before
rows. Journal attempt and completion records durably, fsync at row boundaries;
completed IDs are unique. A crash after GPU computation but before a committed
row completion leaves that attempt incomplete and may repeat that row only.
Resume only after verifying every completed row's identity, full input/header,
profile/config/source equality and journal integrity in a fresh preflighted
process. Skip completed successes AND terminal failures; no mixing profiles.
Preserve a truncated final record separately for audited recovery rather than
silently discarding bytes. Corruption in an earlier record stops recovery.
Time/status history is separate from the canonical sorted final score ledger.
Partial, missing-ID or inconsistent runs cannot publish a calibration/freeze.

Verify threshold/artifact deterministically from the same persisted valid-score
ledger; canonical scientific outputs must match byte-for-byte across independent
assembly. Before real dev work, verify fresh-process repeat scores on the existing
B2 synthetic input fixture under the final F hash, with no numeric source edits.
Also repeat a fixed predeclared first 10 dev-human rows in a new process solely
as a reproducibility audit, stored separately and never added twice to N. Compare
terminal status/reasons and require exact statistics/scores/window/hash agreement
for valid results; a failed row is not replaced by its audit attempt. No selecting the better run,
no averaging or tolerance that hides changed decisions. On mismatch stop before
publication, preserve both results and investigate without test access.

## 9. Committed freeze and R1-G boundary

Freeze record proposed at eval/freezes/r1f_freeze.json, after complete valid dev
ledger, count gate, calibration validation and reproducibility checks. Bind:

- Calibration artifact byte/canonical digest, exact 5% c, strict comparison,
  score direction and actual N; 1% explicitly disabled.
- Exact final scoring_config_hash, full fields, normalized scorer sources/list,
  implementation commit, runner/script/validator hashes and execution profile.
- E scientific manifest and dev-projection identities, explicit historical
  source reconciliation digest, final dev-score/failure ledger digests and counts.
- Lexicon names/versions and exact raw-file SHA-256, including current reviewed
  claim_phrases_to_inspect, hedges and stock_phrases; bind observer source/version
  identities even though lexicons never influence origin/calibration thresholds.
- Calibration creation/procedure/schema version and relevant evidence digests;
  inherited historical transfer exception, explicitly not proof of compliance.

Current lexicon hashes for review (re-read via the packaged loader at freeze):

| Name | SHA-256 |
|---|---|
| claim_phrases_to_inspect | 6ef25f0591733bd04d317d29fbdf82bba1dd311dea6b2eb320c45cfd260ee705 |
| hedges | d2625f88fa1b9ac4b784590fa3e16128791e35c71ee606f8cfd079123da09805 |
| stock_phrases | 781b44148b65ac55fa394cc87ab8947e36f13e3ed7d56d3ff8045251c974d637 |

No self-referential Git hash: record the source implementation commit; commit the
calibration, ledgers, validation evidence and freeze together; report the actual
containing freeze commit on readback. Require clean Git, tracked-artifact byte
matches and reviewer confirmation of that committed freeze before any G scoring.
Pure validate_freeze supports mismatch tests now, but **F does not implement/run
a test scorer**. Future G must validate committed freeze/config/threshold/data/
lexicon identities before opening any test blob and append every test access to
its run log. A modified threshold/config/source/lexicon/data identity invalidates
the freeze; stop for a new authorized freeze rather than editing it after test
access. No held-out metric or test score is an input to this record.

## 10. Ordered implementation/verification tasks after approval

| Step | Work and acceptance evidence |
|---|---|
| F0 | Synthetic tests for dev-only projection, exact source reconciliation, profile/hash completeness, threshold rule and artifact schemas; fix minimum code owners above |
| F1 | Implement creation/validated application, journal/resume and freeze validator; model-free scorer/report/CLI tests; lock source list; commit stable implementation before any dev score |
| F2 | Fresh-process local CUDA preflight and existing synthetic B2 repeat check; save actual profile/hash, asset IDs, memory/time and guard observations; stop on incomplete/drift/error |
| F3 | Verify unchanged E/dev identity, load only dev blobs, produce durable score ledger; independent fixed repeat audit; reconcile all role/failure counts and actual N>=200 |
| F4 | Select exact 5% c from valid humans; independent ledger reassembly and threshold recomputation; validate artifact and report projection; no 1% or test scoring |
| F5 | Assemble/validate freeze; update actual interfaces/README/decisions with limitations; commit artifacts/evidence/freeze, read back hash/status and stop for independent review |

Required synthetic tests: 199/200 negative gate, 1% refusal, no negatives,
all-equal/repeated/boundary ties, N not divisible by 20, negative/zero oriented
scores, higher/lower directions, strict equality, independent brute-force
candidate oracle, permutation invariance, no rounding/interpolation, non-finite/
bool/unknown-direction rejection; a hand-computed calibrated report test.

Artifact/consumer tests: malformed JSON/duplicate keys/schema, wrong config
digest/source/profile/manifest/ledger/direction/N/c, nonminimal c, ambiguity,
CPU/incomplete profile/driver unavailable, source drift before/resume/during
scoring, calibrated pass/tie/below-threshold results, missing artifact and unchanged
default/quality/C2PA/image behavior. Report serialization and CLI use fake scorers
or constructed artifacts, explicitly not real calibration evidence.

Runner/freeze tests: injected test row/call/blob access denied, no test-score-file
discovery, raw/window hash mismatch, duplicated/missing row, terminal failure
accounting and valid-human independence from failed positives; crash at every
journal boundary, truncated suffix versus earlier corruption, stale lock,
duplicate writer, incompatible resume, no overwrites, mismatched lexicon/source/
artifact/data freeze refusal, uncommitted/tampered artifact refusal. Use all-socket
blocking mocks/fresh-process guards, not live traps under the no-network scope.

At completion run relevant model-free tests inside/outside the repository,
Ruff on src/tests/scripts, pip check, whitespace checks and scoped source audit.
Full default tests include live loopback controls: do not run those without an
explicit later relaxation; record exact selected checks and omissions. Run only
the approved CUDA synthetic/dev F checks, not the whole slow/model/test suite.
Record commands, exits, counts and errors; no success inferred from past review.

## 11. Runtime/storage estimates and stop conditions

Existing synthetic evidence only: eval/results/r1b2_benchmark.json measured
512-token end-to-end mean 0.21739 s and p90 0.22547 s per row, roughly 3.65–4.01 s
model load plus ~2.2–2.35 s imports; peak allocated 5,854,253,568 bytes and reserved
7,774,142,464 bytes on the RTX 4060 Laptop GPU. It did not measure these dev texts
or the final F hash. At 1,484 rows all at the 512-token mean, score time alone is
about 323 s (5.4 min), or ~335 s at that old p90 rate. Allow roughly **10–20 min
for one complete F run including local verification/journaling**, and **20–40 min
for preflight/repeats/independent artifact verification**; estimates, not caps or
new measurements. Actual throughput, GPU pressure, thermal state and I/O may differ.
No CPU fallback, precision/batch change or new sample size to meet this estimate.

Keep score/statistic metadata small (proposed <=100 MB incremental F artifacts);
no raw-text duplication, logits, model copies or dependency downloads. Measure
actual elapsed/CPU, GPU allocated/reserved peaks, row rates, failures and disk
use. Keep existing ignored data and models. Raw-text redistribution remains
forbidden. Prior 25 GB E artifact ceiling/transfer history is not retroactively
revalidated by these estimates or a successful F run.

Stop on missing approval, prepared/dev/source/config mismatch, unavailable or
incomplete production profile, test access, unexpected networking, systemic GPU
failure, irreproducibility, corrupt journal, unknown artifact semantics or actual
N<200. Preserve evidence; never repair these by reselection, unknown-profile
matching, data imputation, seed search or inspecting test scores. F completion
means a verified committed freeze submitted for independent review, not permission
to run G. This plan remains proposed until explicitly approved.
