# R1-G held-out evaluation plan

**APPROVED by Ryan at 8afab9e, 2026-11-01: G0–G5**, including local CUDA preflight
and the held-out pass. Lock the specified bootstrap/seed/shared draws, failures,
metrics and slice rules before access. Commit tested G code outside frozen F/E
paths before opening test blobs; require every accepted identity/profile gate.
No interim performance inspection, tuning, recalibration, reselection, frozen
source edits, network, dependencies, UI or extra scope. Stop on identity/profile/
integrity/systemic failures. Execution ends with committed evidence and review.
Original proposal/status text below is historical; actual results are separate.

## 1. Goal, authority and accepted baseline

After separate approval, perform one held-out scoring pass at the accepted fixed
configuration/threshold, compute the specified clean and paired-attack statistics
with grouped uncertainty, and publish counts, failures and limitations honestly.
Do not choose methods, thresholds or reporting slices from held-out outcomes.

Precedence: Ryan's explicit instructions/corrections; R1-PLAN-CORRECTIONS-A.md
(especially CA2); approved R1-PLAN.md sections 1.1–1.3 and G; SPEC sections
10.1–10.9; Addenda A/B where not superseded; accepted E/F plans and interfaces.
Old draft/OPEN/approval labels describe their original dates. Later approvals
and reviewer-reported closure are recorded in docs/decisions.md.

Planning baseline: clean master at **bf455659053cca15ec82cb85065613c6b7459a44**.
No repository AGENTS.md found. Ryan supplied independent R1-F review: 539 selected
model-free tests, Ruff and pip check passed; committed-freeze validation passed at
that commit; independent ledger/threshold checks confirmed 1,484 unique valid dev
rows, 298 human negatives, c=-0.9272342324256897, 14 strict exceedances and one
unflagged tie. **R1-F is closed on reviewer-reported evidence.** This is not a
builder rerun of those tests and does not authorize G execution.

Keep the E historical transfer-accounting exception narrowly scoped: original
cumulative transfer compliance remains unproven. Preserve all receipts, prepared
data, F implementation/calibration/development ledgers and freeze bytes. No
network (including live loopback controls), reacquisition, reselection, seed
change, tuning, new calibration, 1% threshold, CPU fallback, UI or dependencies.
No quality-detector evaluation or later-checkpoint work is added.

## 2. Frozen identities and source boundary

Use these exact accepted anchors, checking bytes against the accepted F commit,
not assuming current HEAD must remain that commit after G code is added:

| Identity | Value |
|---|---|
| Frozen scorer implementation commit | 047421cf4c36f8a946453eacc1b9c056bf5147d6 |
| Accepted freeze/artifact commit | bf455659053cca15ec82cb85065613c6b7459a44 |
| scoring_config_hash | 10f0fa316fa5f3d87c7819f86f09ecedc5bc5b1b71e9250d8586aece7390db2f |
| Freeze file SHA-256 | 2b052f43f4f8b487968a1f1e7815630c1ea6fb1e523d2957239b21afe1156ba7 |
| Freeze canonical payload SHA-256 | 48035a7984482a325349b32b746a3463534089849254141da61a2a019ce228aa |
| Calibration file SHA-256 | edd84087ab56d25d43df653cdaaaa2f06dccdb196108c32c67c9e1a505822134 |
| Calibration payload SHA-256 | 3d779223c5c3779ff82ae1ce169b4c07ec59a3571b38b2d5463b28a8516be2c8 |
| E prepared-manifest payload SHA-256 | 8f0a36e95e9745e27bd444b94fe96381c5c0cd98744b2abd52bd2a6ce579c5d9 |
| E test-projection SHA-256 | af6959b6ff803b9e60ea2408e6a0305577f1641c10f884429991f84332c30348 |
| Explicit E source-reconciliation file SHA-256 | 836baccb57a834bca3c3fcd9e28862c1dbcf99879f6a22b008d3afc867d5a851 |

Paths: eval/freezes/r1f_freeze.json; the exact hash-named calibration under
calibrations/; eval/manifests/r1e/primary/; and
eval/results/r1e_budget_fix_source_reconciliation.json. Freeze -> calibration
file/payload digest stays one-way. Do not add G hashes back into accepted F files.

The nine fixed SOURCE_FILES in scorer/identity.py determine scoring identity.
The freeze additionally binds 14 implementation paths, five quality-source files,
three lexicon identities, development inputs/ledgers and evidence. Preserve ALL
of those byte identities, not just the nine scorer sources. E reconciliation
also covers its separate historical/current preparation source maps. No source
list expansion, compatibility alias, unknown-profile matching or changed c.

G implementation must be outside these frozen paths. Proposed new owners:

| New path | Responsibility |
|---|---|
| src/litmus/evaluation/__init__.py | Minimal package, no model/data side effects |
| src/litmus/evaluation/gate.py | Accepted-commit/freeze/source/config verification, test metadata projection and restricted session |
| src/litmus/evaluation/journal.py | Durable test-access/scoring attempts, one completion per ID, inspected recovery |
| src/litmus/evaluation/metrics.py | Pure fixed-threshold, rank/tie AUROC, paired metrics and grouped bootstrap |
| src/litmus/evaluation/run.py | Thin one-pass orchestration and evidence/metric assembly |
| scripts/evaluate_r1g.py | Explicit preflight/score/verify/metrics operations; no fit/calibrate/tune operation |
| tests/test_evaluation_gate.py, test_evaluation_journal.py, test_evaluation_metrics.py | Constructed/fake-scorer regressions before actual test access |

Reuse frozen load_pair, profile/config hash helpers, BinocularsAnalyzer.score_text,
statistics validation, artifact/freeze validation and generic durable-I/O primitives
read-only where their contracts fit. F production_session/scoring_guards/run_rows
are intentionally development-only: do NOT relabel test rows, monkeypatch their
guards or edit them for G. New G guard/journal policy is needed for the held-out
scope; detector math and calibration decisions retain their existing owner.

Bind G's own code commit, explicit file hashes and evaluation-policy digest in a
separate immutable run header. This identity does not enter scoring_config_hash
or alter the accepted F freeze. Commit tested G implementation and its proposed
policy before the first real test access. Adding new evaluation files must leave
the scorer hash unchanged; verify that with regression tests. If a required change
touches any frozen source/contract, raise it **before any test blob access** and
stop for a new decision. Never change frozen source and retain scores under an
old identity, or silently create a replacement calibration after test exposure.

Tech stack: existing .venv, pinned local CUDA models/tokenizer and stdlib
JSON/hash/random/statistics; no sklearn/scipy/new package. TDD route: auto/strict
for metrics, data-access and persistence boundaries; synthetic scores/fake models
first. Proposed execution inline after approval. No implementation in this turn.

## 3. Gate before held-out text access

1. Check accepted F commit exists; match freeze/calibration/development evidence
   bytes to that commit and validate their schema/digests. Use accepted-commit
   Git blob comparison, not a mutable file merely naming the same hash. Validate
   all frozen source maps, source normalization/list, lexicon versions/raw hashes
   and quality-source identities. Do not re-read dev text or recalibrate.
2. Validate E envelope/ledger/split hashes and metadata invariants, with explicit
   unchanged historical source reconciliation. The test projection is canonical
   retained-row JSON plus LF for split=test in retained order, exactly the E
   split-digest rule. Do not scan raw train.csv, indexes or re-run selection.
3. Metadata-only expectations: **675 groups / 3,361 rows**: 675 clean humans,
   675 clean machines, 675 homoglyph, 661 paraphrase and 675 zero_width_space.
   Existing missing attacks stay missing. Verify IDs, parents, roles, groups,
   slice metadata, counts and exact test-projection digest. Unknown, duplicate,
   injected dev IDs, changed links or changed population stop before opening text.
4. In a fresh process, block all Python connections/name lookups and process
   launches during loading/scoring; use only local assets and offline settings.
   Verify models.manifest.json pins, sizes/hashes and tokenizer identity. Load the
   production pair explicitly on CUDA, batch1/eager/fp32, TF32 off/highest,
   deterministic algorithms true, :4096:8 configured before CUDA initialization.
5. Read back full production profile and compute the unchanged production
   scoring_config_hash using frozen helpers. Require exact fields/hash matching
   the accepted artifact, complete CA2 metadata, RTX4060Laptop/driver572.60/
   CUDA12.4 and the accepted pinned libraries. Missing driver, preinitialized
   context, CPU, changed libraries/settings/source or ambiguity stops. Never
   reapply settings to conceal drift. Capture preflight evidence before test I/O.
6. Use the existing committed B2 synthetic input for numerical sanity/repeat
   comparison with accepted F preflight values, not a test row as warm-up. No
   held-out repeat audit is permitted. Synthetic/profile mismatch stops G.
7. Create/fsync the immutable G header, evaluation policy, metadata-only test
   projection and access journal. Only after all gates pass may a single-writer
   scorer open an allowed test blob. Tests must prove every gate failure causes
   zero test-file opens and zero test scorer calls.

Preserve separate IDs: frozen F implementation commit, accepted freeze commit,
and new G evaluation-code commit. New G code must not masquerade as the original
scorer source or cause a change to the calibration hash. Full numerical profile
and source checks recur before each row, after each call and at resume/end;
the frozen analyzer's own effective-setting checks remain active.

## 4. One-pass scoring, access logging and interruption recovery

Allow only exact test blob paths from the immutable test projection. Deny raw
CSV, SQLite, dev/repeat blobs and arbitrary data paths in G's scoring context.
Path containment and identity checks precede interpretation. Do not glob texts
or infer split/labels from a filename. Lexicons are identity-bound but no quality
observations are computed for this origin-evaluation checkpoint.

For each ID in fixed retained order: fsync an access/attempt intent **before**
opening its blob; read bytes once, verify raw hash, strictly decode UTF-8 without
newline/Unicode normalization, and validate E eligibility/window identity with
the unchanged tokenizer policy. Record access outcome/hash and call the frozen
production scorer on that in-memory string. Use the validated fixed calibration;
require returned fields/hash/profile/window/statistics and Calibration projection
to agree with the freeze. Check returned flag independently against r>c. Finiteness,
ratio/count guards remain mandatory. Fsync one terminal completion for that ID.
No raw text, token arrays or logits are committed.

Access log entries include row/source ID, attempt sequence, operation/reason,
input/source/profile/run identities, timestamps, open outcome and completion/
failure; all actual opens, including authorized interrupted-row recovery, are
accounted. Verification/metrics use the ledger and metadata, avoiding another
test-text pass. Do not inspect test scores before the scoring run finishes;
progress exposes counts/failures only. Do not look at interim performance to
stop, tune, choose rows or change the protocol.

One-pass means one accepted terminal score per immutable row ID. Physical
exactly-once forward execution cannot be guaranteed across a crash after GPU
work but before durable completion. Disclose this explicitly: only the unfinished
row may be recomputed under identical frozen identities, with both attempts logged;
do not claim it was necessarily computed only once. Completed rows, including
terminal failures, are never rescored or replaced. No first-ten-test repeat audit.

Use exclusive ownership/lock tokens. Resume validates the complete journal,
header, source/config/profile, input projection and all completed row records,
then continues missing IDs in the same order; duplicate completions or gaps fail.
A stale lock is reported for inspection, never silently deleted. Preserve any
truncated last record/entire damaged journal before explicit recovery; validate
the preceding complete records, and do not repair earlier corruption. A profile
or identity change is not a recoverable resume under the old run. Never switch
device, precision, batch size or method to finish the run.

Proposed row-failure policy for review: a production-reported numerical score
error is a terminal failed row, with no score/flag, **only if** pre/post source and
session checks still establish the accepted identity. Continue the fixed pass
without retrying that row. Unknown exceptions, CUDA OOM/context errors, integrity/
window/profile changes or a failure in the numerical-validation machinery itself
abort the run as incomplete. Preserve failed/pending records; do not manufacture
no_signal, zero scores or successful results. This G failure policy does not
retroactively change F's calibration-creation stop rules.

Report every requested row as valid, terminal failed, pending or not attempted,
by role/domain/generator/attack. No headline completed-test result from a partial
run. After a complete pass, metric-specific valid denominators and coverage are
explicit; scores excluded for failure are not silently treated as correct negatives.
No new content-based exclusions, pair cleanup, refill or group movement.

## 5. Fixed-threshold primary metrics and paired attack comparisons

Frozen rule: r=-raw_score; flag iff r > **-0.9272342324256897**, equivalently
raw_score < **0.9272342324256897**. Equality is unflagged. Alpha label=5%, not a
promise that held-out FPR will be <=5%. Never derive a test threshold, optimize
F1/Youden/accuracy, recalibrate, use a 1% operating point or round before comparing.

Primary clean metrics:

- AUROC on valid clean machines (positive) versus valid clean humans (negative),
  using r oriented higher=more-machine. All positive-negative comparisons count
  1 if r_positive>r_negative, 0.5 if equal, 0 otherwise. Do not include attacks
  as extra positives in the primary clean AUROC.
- Clean TPR=flagged valid clean machines / all valid clean machines.
- Actual test FPR=flagged valid clean humans / all valid clean humans.
- Show numerator, valid denominator, total requested count, unique contributing
  groups and failures for every statistic. Individual valid clean rows remain
  usable when their counterpart fails; do not condition primary FPR on machine
  success. Results are conditional on score validity when failures occur, with
  coverage/failure counts alongside rather than concealing selection by success.

Implement AUROC by a tie-aware rank/score-block method, cross-checked against a
fresh small pairwise oracle. For weighted bootstrap, process each score block with
positive weight P, negative weight N and cumulative negative weight below L:
contribution=P*(L+0.5*N); divide by total_positive_weight*total_negative_weight.
This retains all Cartesian multiplicities, including k^2 comparisons when a
group's positive and negative are each repeated k times. No score binning or
epsilon ties. Missing class => null with status undefined/missing_class, not 0.5.

For each of paraphrase, homoglyph and zero_width_space, join only the frozen
adv_source_id to its selected clean machine in the same source group. The paired
set requires both scores valid; report original availability, missing attacks,
failed parents/attacks and actual valid-pair denominator. On that SAME set report:
clean detection rate, attacked detection rate, paired difference (attacked-clean),
and four paired outcomes (both flagged, neither, clean-only, attacked-only).
Do not compare attacked detection rate against the unrelated overall clean TPR.
Retain and label existing raw/window no-ops; no outcome-based exclusion. Missing
or failed pairs contribute to coverage/failure accounting, not fabricated flags.

Exploratory slices are fixed now: clean metrics by domain (8), assigned generator
(11), selected-machine decoding (2), selected-machine repetition penalty (2),
plus the 8x11 domain/generator cell table. Paired attack metrics overall and by
domain/assigned generator; do not add post-hoc favorable cross-products/rankings.
Assign each group's human to its frozen clean machine's cell for slice membership;
the human's own model label remains human. Otherwise per-generator AUROC would
incorrectly discard every negative. Publish empty slices/counts too. These are
descriptive, correlated comparisons, not multiple hypothesis tests or tuned claims.

## 6. Grouped bootstrap, multiplicity and undefined/small slices

Use SPEC 10.7 exactly: **1,000 replicates**, drawing **G=675 source groups** with
replacement from the fixed test-group universe, jointly across classes and attack
arms. A selected group contributes every row/status it owns; draw count k gives
every member multiplicity k. Failed/missing members stay failed/missing, and
metric validity masks apply within each statistic. Do not drop empty/failed groups
from the sampling universe or resample positive/negative/attack arms separately.
Never resample dev/calibration or recompute c inside a bootstrap replicate.

Proposed fixed bootstrap encoding for approval (not executed now): sort the 675
source IDs lexicographically; seed=**20261030**, independent domain tag
`litmus/r1/bootstrap/v1`; initialize stdlib random.Random with the big-endian
integer SHA-256 of compact UTF-8 JSON [tag,integer_seed], ensure_ascii=False.
For each replicate, call rng.randrange(G) exactly G times using this single
stream; no seed search, split seed change or extra metric-specific RNG draws.
Record Python version, algorithm/tag/seed, ordered-group digest and the full
replicate index vectors/digest so reconstruction does not depend on assumptions
about random library version compatibility. This is bootstrap randomness, not
reselection of dataset source groups.
Validate exactly 1,000 vectors, each with G integer indices in [0,G), and total
group multiplicity G per replicate; reject malformed/truncated/changed draws.

Reuse the SAME 1,000 group draws for all metrics/slices; apply predeclared slice
masks afterward. For paired attack statistics, each group copy preserves both
arms and the same valid-pair mask. Rates use multiplicity-weighted numerators/
denominators. Weighted rank AUROC must equal a literally expanded tiny resample
in tests. Do not convert the drawn groups to a set or deduplicate repeated rows.

Percentile 95% intervals: use nearest-rank empirical percentiles on each
statistic's sorted **defined** replicates, ranks ceil(V/40) and ceil(39V/40),
1-indexed, where V is that statistic's defined replicate count. Record V and
undefined count/reasons separately for every statistic. Exactly 50 undefined
of 1,000 is allowed; **more than 50** suppresses that interval with
"interval not reported (unstable resampling)" plus its defined point estimate.
A missing point-estimate denominator/class stays undefined, not a success or 0.

Apply SPEC 10.8 before interval reporting: a clean slice with <30 contributing
unique groups OR <50 valid rows in either class has counts and any defined point
estimate only, labeled "insufficient data; no interval". Missing one class makes
AUROC undefined; any otherwise defined rate may still have a point estimate, but
does not bypass the slice's interval suppression. Report valid class counts.

For the positive-only paired attack contrast, the proposed conservative analogue
is >=30 contributing groups AND >=50 valid pairs (>=50 rows per arm) before a
paired interval is reported. Its rate/difference does not require an artificial
human class; attack-only AUROC is not computed. This operationalization is part
of this proposal for review, not an asserted extra rule in SPEC. Undefined-pair
replicates are counted for that contrast separately.

Intervals are conditional on frozen calibration and this prepared sample;
calibration uncertainty, multiple exploratory slices, source-corpus/pretraining
overlap and domain shift are stated limitations. No assertion of guaranteed 5%
test/population FPR and no significance claim from overlapping/nonoverlapping CIs.

## 7. Artifacts, reproducibility and honest README reporting

Proposed new outputs only: eval/results/r1g/{header.json,test_input.jsonl,
access.jsonl,journal.jsonl,scores.jsonl,failures.jsonl,counts.json,
bootstrap_groups.json,bootstrap_draws.jsonl,metrics.json,verification.json},
plus a separate G summary. Keep canonical UTF-8/LF metadata, sorted identities,
nonrecursive payload digests and separate timing/attempt history. Add G-only
.gitattributes rules if needed without changing any frozen F bytes.

Bind accepted F commit/freezes/artifact, scorer hash/profile, E/test/reconciliation
identities, G code/policy commit/hash, source-group list, metric definitions,
failure masks, seed/RNG/draws, scores/failures/access ledgers and counts. No raw
texts, token arrays, logits, weights or copies of the dataset in Git. Retain all
original F/E evidence; new summaries must not overwrite their closure receipts.

Reproducibility verification reassembles metrics/intervals from the same complete
immutable score ledger and saved draws, independently checking formulas on toy
oracles. It does NOT perform a second real held-out scoring pass or read test
texts again. No G source edits during scoring. A later pure metric-code bug fix
must preserve the original result/version, use the same immutable scores/draws
and regression evidence, never rescore or change predeclared estimands/slices/
seed/threshold; any definition change after results are known stops for review.

README results may be written only after the complete verified run. Show accepted
configuration/freeze and new evaluation commit, actual groups/rows/class counts,
coverage/failures, clean AUROC/TPR/**observed** test FPR, applicable CIs with V/
undefined/small-slice labels, and paired attack rates/deltas on identical pair
sets. Separate primary from exploratory results, missing/undefined/not-run from
zero, and development 14/298 from actual held-out results. Report disappointing
results as plainly as favorable ones; do not hide failed generators or attacks.
Do not claim broad AI detection accuracy, human origin, calibrated probabilities,
new calibration or external validity. Quality observations and C2PA limitations
remain unchanged. Historical transfer-cap compliance is still unproven.
This is Litmus's held-out source-group subset of the approved RAID train.csv,
not the publisher's unlabeled test.csv and not an unseen-generator protocol.
The same generator families can occur in dev and test; do not claim otherwise.

## 8. Ordered tasks and tests after separate approval

| Step | Proposed work / acceptance |
|---|---|
| G0 | Lock this policy and metadata projection; synthetic tests for identity gates, metrics/ties/multiplicity/undefined/small-slice rules and durable journal |
| G1 | Implement only new evaluation package/script/tests; confirm all frozen sources/artifacts unchanged and scorer hash unchanged; commit stable G implementation before test access |
| G2 | Fresh local CUDA/profile/assets/frozen-commit gate and existing synthetic sanity check; save exact preflight/header/access-log readiness; zero test opens before PASS |
| G3 | One terminal result per fixed test ID, durable access/scoring log and allowed recovery only; complete count/failure reconciliation; no interim performance inspection |
| G4 | Fixed-threshold clean/paired metrics, one shared grouped-bootstrap draw set, predeclared slice suppression; independent pure reassembly from immutable scores |
| G5 | Honest README/interfaces/decisions and metadata-only evidence; commit results/evaluation provenance, read back hashes/status and stop independent review |

Tests before access: wrong accepted commit/freeze/artifact/config/profile/driver/
source/lexicon/dev-or-test projection => zero blob opens; new G sources leave
scorer hash unchanged; attempted use of F dev guard rejects test data; dev/test
path injection, changed raw/window identity, duplicate/unknown ID, no-log access
and incomplete/invalid calibration => fail closed. Use in-memory fixtures/fake
scorers/all-socket guards, never real held-out text in default tests.

Journal tests: crashes before access, after read, after forward but before durable
completion, duplicate writer, stale lock, repeated pending attempt, terminal
failure not retried, truncated tail preserved/recovered, earlier corruption and
profile/code mismatch refused. Count physical attempts separately from terminal
scores; demonstrate completed rows are skipped on resume.

Metric tests: perfect/inverted/all-tie AUROC, both score directions and unknown
direction refusal, exact c equality, nonfinite/bool/missing score handling, zero
denominators, failed positive not dropping valid negative; matched-parent joins,
missing/failed attack pairs, same-window no-op, paired-arm discordance/delta sign;
weighted bootstrap versus expanded repeated-group oracle, zero-weight/missing
classes, shared-draw masks, deterministic draw goldens/reconstruction, percentile
ranks, 50 versus 51 undefined replicates, and 29/30 groups plus 49/50 rows/pairs
boundaries. Reassembling metrics may not mutate c, create a calibration or call
a model.

Run relevant selected model-free tests inside/outside, Ruff, pip check, whitespace,
scoped source audit, frozen-byte/hash preservation checks and new evaluation
CLI/report round-trip tests. Omit live network controls/full slow suite and record
exact omissions. No installed GPU portability claim. Use approved real CUDA only
for local preflight and the single held-out procedure, not threshold experiments.

## 9. Estimates, failures and stop state

F's recorded primary 1,484-row procedure took 274.489 s including its local
asset/model/journal work; synthetic B2 512-token mean was ~0.21739 s. For 3,361
rows, linear estimates are ~622–731 s (10–12 min) before extra G gate/logging
costs. Budget roughly **15–30 min for a normal scoring pass** and **10–30 min
for verification/bootstrap/report assembly**; estimates, not measurements or
reasons to change batch/precision/sample/replicate count. F measured GPU allocated
peak5,854,253,568 bytes and audit reserved peak7,203,717,120; current availability
and G peak are unknown. Record actual elapsed/CPU/GPU/disk and failures.

Propose <=100 MB new metadata artifacts, including saved draws/access attempts;
no raw copies or model downloads. Use weighted/rank computation rather than a
large expanded data matrix. Preserve partial work and disclose interruptions;
do not destructively clean data or restart an evaluated sample as a new unseen run.

Stop before access on missing approval or any frozen identity/profile mismatch;
raise required frozen-source changes before exposure. Stop scoring on corruption,
unexpected networking, systemic CUDA/error/identity failure or a code/policy
change. Incomplete runs are incomplete, never selectively reported as the full
test set. No threshold tuning/new calibration/reselection can repair G results.
Completion is a verified committed evaluation submitted for review, not permission
for UI/later work. The original proposal was approved for G0–G5 at 8afab9e;
the implementation and completed results are submitted for independent review.

## 10. Execution receipt (2026-11-01 local; UTC receipts extend into November 2)

Stable G code/policy b5cdc56d14a063d56683d825cef7c7ecdaac69b4 preceded all test
access. G0–G5 executed without frozen F/E edits, threshold/config changes, network,
reselection, new dependencies or recovery. Fresh CUDA/synthetic and every accepted
identity/profile gate passed. All 3,361 rows/675 groups were valid, from 3,361
attempts/reads; zero failures, pending/not-attempted IDs or guard blocks.

Clean AUROC0.8035775034293553; TPR448/675; actual test FPR31/675. Matched attack
valid-pair counts675/661/675 (homoglyph/paraphrase/zero_width_space); 14 original
missing paraphrases retained as missing and one paraphrase window no-op retained.
All 112 clean/60 paired slices and fixed shared-draw intervals are saved, including
small-slice suppression. Independent expanded formula reassembly matched all
results/intervals from saved ledgers/draws with no test rereads or rescoring.

Scoring wall5,303.18972689996s / CPU4,966.84375s exceeded the estimate; no causal
profiling or gate relaxation was performed. Actual full-precision results,
resources, verification commands/omissions and limitations are recorded in
eval/results/r1g/, eval/results/r1g_verification.json and README. No G source
changed after test access. Original E/F evidence and historical transfer exception
remain intact; original cumulative-transfer compliance is still unproven.
**Submitted for independent review; R1-G is not independently closed.**
