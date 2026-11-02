# R1-E — RAID data preparation plan

**CLOSED, reviewer-reported, 2026-11-01.** Ryan supplied independent Codex review
of correction commit d50b7e0: 68 offline RAID tests, Ruff, pip check and whitespace
passed; all 26 historical evidence files are preserved; both runs' source
reconciliation validates and scientific files match. Closure retains Ryan's
specific historical transfer-accounting exception. **Historical cumulative
transfer compliance remains unproven.** This supersedes the historical STOP/
pending-review status below without rewriting receipts or source identities.
R1-F-PLAN.md is proposed for separate review; no scoring is authorized by closure.

**APPROVED by Ryan on 2026-10-31: E0–E6 data preparation and bounded acquisition
only.** Seed 20261030, N_target=1,000, attack tie-break, hash encodings,
metadata-only selection and no refill after exclusions are explicitly approved.
The original planning detail below is retained as the approved procedure, with
execution outcomes to be recorded separately. Review alongside
[the acquisition request](R1-E-ACQUISITION-APPROVAL.md).

**Execution status (2026-10-31):** primary preparation retained 973 groups and
4,845 rows, including 298 development human texts. Final verification evidence
is indexed in `eval/results/r1e_verification.json`. Independent R1-E acceptance
is pending. **STOP: final adapter inspection found that urllib reads redirect
bodies outside Budget.read. The recorded counters cover API/artifact reads but
cannot establish the full cumulative transfer cap. No actual overrun is proven;
R1-E is not complete or accepted.** See `r1e_redirect_budget_audit.json` under
eval/results/. No reacquisition or source patch was performed after this finding.
The original planning statements below (including unknown counts,
absent CA1 implementation, proposed seed and unfetched payload) describe the
planning session, not the current execution state. Ryan's approval above and
the execution evidence supersede those status statements without changing the
approved selection procedure. R1-F and R1-G remain separately gated.

**Approved follow-up exception:** Ryan subsequently accepted only the specific
historical transfer-accounting uncertainty and authorized an offline downloader
correction plus explicit source-version reconciliation. This supersedes the
operational STOP above, not the historical uncertainty: **the original transfer
is not proven to have met the 13 GB cap**. Original receipts, scientific files
and generation-source hashes are preserved. Existing data/selection are retained;
no reacquisition, further network requests or real-data reselection is permitted.
R1-E remains pending independent review. Follow-up evidence is separate in
`eval/results/r1e_budget_fix_verification.json`; prior evidence is not rewritten.

## Authority and boundary

Baseline: `d7ed91fc949087cee271ac51dcc058bc2a115f48`. Ryan supplied independent
D3 review results: 660 default tests, Ruff, pip check, whitespace and a fresh
installed-wheel check passed. D3 and R1-D closure are recorded as
reviewer-reported evidence, not tests rerun for this plan.

Precedence: Ryan's later explicit approvals/corrections, then
`R1-PLAN-CORRECTIONS-A.md` (especially CA1), `R1-PLAN.md` sections 1.3 and 2,
SPEC Addendum B3, Addendum A3, and SPEC sections 6.1–6.2 and 10.2–10.4.
The original documents' earlier approval-status lines are historical; actual
checkpoint approvals are in `docs/decisions.md`.

- **APPROVED:** N_target = **1,000 source groups**, recorded 2026-10-30 after
  R1-B2. This is the initial selection target, not 1,000 rows, not a promise
  of 1,000 retained groups, and not approval to acquire data.
- **APPROVED:** seed **20261030**; fixed before acquisition or selection.
- **R1-E only:** acquire an explicitly approved artifact, select by metadata,
  validate/tokenize selected texts, deduplicate, clean pairs, write manifests.
- **No scoring:** no weights, forward passes, logits, Binoculars statistics,
  thresholds, calibration, test evaluation or performance-based selection.
  Tokenization for eligibility/window identity is preparation, not scoring.
- No new dependencies, dataset package installation, RAID attack generation,
  UI or later-checkpoint work. C2PA defaults/results are unaffected.

## 1. Acquisition identity, evidence and costs

### Proposed artifact pin

Use the authors' Hugging Face dataset repository `liamdugan/raid`, revision
**865cac74188466cb0c3b7574a10204007b57a459**, file **train.csv** only. The
[immutable revision page](https://huggingface.co/datasets/liamdugan/raid/commit/865cac74188466cb0c3b7574a10204007b57a459)
and [revision tree](https://huggingface.co/datasets/liamdugan/raid/tree/865cac74188466cb0c3b7574a10204007b57a459)
were inspected on 2026-10-30. They identify the revision and file, not a locally
verified download. Never resolve mutable `main` during the approved run.

Proposed future payload URL (listed for review; not fetched):

`https://huggingface.co/datasets/liamdugan/raid/resolve/865cac74188466cb0c3b7574a10204007b57a459/train.csv`

Publisher-advertised expected identity:

- bytes: **11,779,491,051**;
- SHA-256: **52f04ceebc126064e68fbd22d8b736964065745464f4bfd52e488150b49f84e4**.

The exact byte count/digest appear in the immutable
[train-file addition commit](https://huggingface.co/datasets/liamdugan/raid/commit/6749693cab9ccb7452a32d575ecb80abff57b2c0);
the [current file metadata page](https://huggingface.co/datasets/liamdugan/raid/blob/main/train.csv)
also advertises that digest. The chosen revision tree lists train.csv, but the
browser could not retrieve its revision-specific blob/pointer page or API.
**Reviewer-confirmed on 2026-10-31:** Ryan reported Codex independently confirmed
the revision-specific API metadata matches this byte count and SHA-256. This
updates the planning uncertainty with reviewer attribution, not builder evidence.
Before payload transfer, the builder must repeat that revision's
small pointer/API metadata and confirm both values above. Stop on mismatch or
inaccessible identity; do not silently substitute main or another file.
Local content verification is recorded only after the approved transfer.

The [official repository](https://github.com/liamdugan/raid#download-raid) also
publishes `https://dataset.raid-bench.xyz/train.csv`. Its
[loader source](https://raw.githubusercontent.com/liamdugan/raid/main/raid/utils.py)
uses that host. This is an official alternative, but the URL is mutable and
cross-host byte equivalence has not been established here; it is not an
automatic fallback. Do not fetch train_none.csv as well: it omits needed attacks.

Use one direct streamed HTTP download with the standard library, no datasets,
pandas, raid-bench installation, Hub snapshot clone or automatic Parquet/Xet
cache. Follow only redirects serving the same pinned artifact; record final
URL/redirect hosts, without persisting signed query secrets. Verify length and
SHA-256 before accepting an artifact. A `.part` file is not valid input.
Resume only after verifying immutable identity and HTTP range semantics.

### License and scope

The [dataset card](https://huggingface.co/datasets/liamdugan/raid/blob/main/README.md)
declares **MIT**. The [authors' code license](https://raw.githubusercontent.com/liamdugan/raid/main/LICENSE)
is also MIT; these are separate observations. Preserve source attribution and
license notices after approval. The rights/terms of every underlying source
corpus have not been independently audited here. Request local evaluation use
only, without publishing raw texts or adding them to Git. Litmus's own license
remains OPEN; acquisition does not resolve that decision.

Only labeled RAID-train is in scope. The official documentation distinguishes
it from unlabeled RAID-test and the extra domains. Litmus dev/test will both
come from grouped subsets of RAID-train; never equate Litmus test with the
publisher's test.csv. No extra.csv or test.csv download is requested.

### Resource budget (estimates, not measurements)

| Item | Proposed budget / estimate |
|---|---|
| Payload | 11.779 GB decimal, about 10.97 GiB; published identity above |
| Transfer ceiling | 13,000,000,000 cumulative HTTP payload bytes, including retries; stop before exceeding it |
| Raw local file | 11,779,491,051 bytes after successful verification |
| Preparation storage | roughly 13–20 GB total including raw, indexes, selected texts and audit outputs; actual index/text sizes unknown |
| Disk gate | at least 30 GB free before transfer; stop if incremental task artifacts would exceed 25 GB |
| Time at 50/100/500 Mbit/s | ideal payload-only lower bounds about 31.4 / 15.7 / 3.1 minutes; throttling, retries and disk work add time |
| Paid-service cost | no paid service requested; ISP/connection charges and actual throughput unknown |

The disk check in this planning session reported 419,241,680,896 bytes free
on C:. Recheck at execution; this is not a reserved allocation. The proposed
30 GB reserve covers bounded scratch space, not duplicate full downloads.
Use atomic completion without copying the entire file. Preserve partial or
previous runs rather than deleting them; they count against the budget.
Streaming reduces memory use, not the full-file transfer requirement. A
1,000-group sample still requires the approved full CSV scan.

## 2. Schema contract: documented values versus unverified contents

The following field names and meanings are documented in the
[official card's schema](https://huggingface.co/datasets/liamdugan/raid/raw/main/README.md#data-fields).
This is documentation verification, not inspection of the downloaded CSV.

| Field | Meaning / proposed use |
|---|---|
| id | row-content UUID; exact row identity and deterministic tie-break |
| source_id | human-source UUID; group identity and split input |
| adv_source_id | original-row link for attacked text; join to selected machine id |
| model | generator label; human sentinel handled separately |
| decoding | greedy or sampling |
| repetition_penalty | yes or no; card describes a 1.2 penalty |
| attack | clean/attack label; exact matching only |
| domain | domain code; exact allowlist below |
| title | contextual metadata, not eligibility or selection content |
| prompt | contextual metadata, not selection input or text to score |
| generation | actual row text, including human rows; inspect only after selection |

Documented machine labels are `chatgpt`, `gpt4`, `gpt3`, `gpt2`, `llama-chat`,
`mistral`, `mistral-chat`, `mpt`, `mpt-chat`, `cohere`, `cohere-chat`.
The [official site's viewer](https://huggingface.co/datasets/liamdugan/raid)
exposes `human` and clean `none`; the card's lists
omit those sentinels. Verify their exact CSV representation before selecting.
No separate `label` column is assumed.

Exact allowed domain codes, lexicographic order:
`abstracts`, `books`, `news`, `poetry`, `recipes`, `reddit`, `reviews`, `wiki`.
`wiki` is the code for the display name Wikipedia; do not use `Wikipedia` as
a CSV value. Exclude code/czech/german and any other out-of-allowlist domain.
Allowed domains are an English-oriented proxy, not per-row language validation.

Requested attack codes are exactly **paraphrase**, **homoglyph** and
**zero_width_space**; clean is **none**. The card documents these identifiers.
Other documented method codes are number, article_deletion, insert_paragraphs,
perplexity_misspelling, upper_lower, whitespace, synonym, alternative_spelling;
exclude them. Descriptions saying “12 attacks” are not evidence of 12 distinct
adversarial algorithms; count actual labels in the pinned file and distinguish
the clean label. Never regenerate attacks, relabel near matches or infer
parentage from matching text/title/prompt.

**Unknown until the approved CSV scan:** header order/dtypes/null encodings,
human/clean link conventions, ID uniqueness, attacked-row multiplicity per
parent/type, actual train row/group/cell counts, missing links, field-size
extremes, English purity, quotas achievable, eligibility losses and ≥200 dev
human texts. Preview counts/estimated whole-repository counts are not train
population counts. New critical schema semantics require review, not guessing.

## 3. Before real data: CA1 prerequisite

No implementation of CA1 keys/tests was found in the current checkout. Do not
claim that precondition is already satisfied. After explicit implementation
approval, deliver and verify this prerequisite **before acquisition or selection**.

Exact encoding from Corrections A:

`key(tag, seed, item_id) = SHA256(UTF8(JSON([tag, seed, item_id])))`

JSON uses separators `(',', ':')`, ensure_ascii=False, integer seed and string
item_id. Preserve IDs exactly; no locale sorting, casefolding, trimming or
ambiguous concatenation. Reject incorrect types, including bool as a seed.

| Independent tag | Purpose |
|---|---|
| litmus/r1/select/v1 | source ordering within a domain |
| litmus/r1/split/v1 | dev/test assignment by source_id |
| litmus/r1/row/v1 | machine-row tie-break by id |

Required pure tests: hard-coded golden digests against independently specified
canonical byte strings; all three tags differ on fixed inputs; Unicode and
concatenation-ambiguity probes; deterministic order independent of input order;
split boundary cases. For 100,000 synthetic IDs, take the 1,000 lowest select
keys; their independently computed split dev share must be in **[0.24, 0.36]**
(proposed fixed ±0.06 tolerance, about four binomial standard deviations).
Fix seed/tolerance once, report the actual fraction, and never retry seeds to
make the test or dataset pass. These tests are proposed, not run now.

## 4. Ordered preparation algorithm

### A. Verify acquisition and create a metadata-only selection view

1. Require recorded acquisition approval, verified pin/length/digest and CA1
   tests. Save an acquisition receipt. Reject HTML/error bodies, LFS pointers
   mistaken for CSV, missing columns and malformed records.
2. Stream the complete local CSV with a real CSV parser, strict UTF-8 (an
   optional file-level BOM may be handled and recorded), newline='' so quoted
   embedded newlines survive. Do not strip BOMs/newlines inside generation.
   Use a bounded, documented field limit; an exceeded limit stops the run
   rather than silently skipping the remainder. A plain line-split parser is
   invalid. No unrestricted read_csv/DataFrame or whole-file materialization.
3. Persist only selection metadata from id, source_id, adv_source_id, model,
   decoding, repetition_penalty, attack and domain in a standard-library SQLite
   index. Count all scanned rows/categories and metadata errors. No hashing,
   language inspection, tokenization or eligibility examination of generation,
   title or prompt is permitted during selection.
4. Transport/CSV decoding inevitably passes through text cells in this monolithic
   file. “Metadata-only” means the selector never receives/uses generation
   content; the projection discards it immediately. It does not claim the
   network avoided transferring text or the CSV parser never decoded it.
5. Duplicate row IDs with ambiguous identity stop the run. Reject sources with
   ambiguous clean human identity or inconsistent clean-domain identity. Preserve
   reasons/counts; do not choose by content. Human = model human and attack none;
   clean machine = one of the documented machine labels and attack none, with
   valid required generation-setting metadata. Nullable human-only settings do
   not make a human row ineligible. Unknown conventions affecting selected roles
   must be resolved explicitly before selection.

### B. Deterministic source-unique quotas, before text eligibility

1. Eligible metadata source: exactly one clean human and at least one clean
   machine row in an allowed domain. Build cells (domain, generator) present
   among those sources, sorted lexicographically. Freeze the eligible frame,
   cell list and its metadata digest before selection.
2. For C cells, q = floor(1000/C); add one to each of the first 1000 mod C
   sorted cells. If C=0 stop with no selectable population. If all 8×11 cells
   exist, this is 32 cells at 12 and 56 at 11; that is conditional, not an
   observed population. This governs over Addendum A3's older equal-domain
   wording: do not impose a second 125-per-domain quota.
3. Within each domain order sources by (select key, source_id). Round-robin
   through sorted cells; each non-full cell takes its next still-unassigned
   source that has that generator. One source may be assigned to only one cell.
   Exhausted cells stop; no quota reallocation or source reuse.
4. Within the assigned source/generator choose the clean machine row with the
   smallest (row key, id), across decoding/penalty variants. Keep the unique
   human. The source gets exactly one clean machine, not one per generator.
5. Assign the group using **split** key only:
   u = int(first 8 digest bytes, big-endian) / 2**64;
   dev if u < 0.30, otherwise test. All its rows inherit this assignment.
   No exact 300/700 quota, split stratification, seed search or split-based refill.
6. Commit/write an immutable candidate ledger before reading selected text:
   source, cell, chosen human/machine IDs, all three keys and split. Account for
   cell shortfalls now; subsequent exclusions never trigger reselection.

### C. Attach attacks without content-based choice

Stream the entire artifact to EOF, retaining only the selected clean IDs and
allowed attacked rows whose adv_source_id equals the chosen clean machine id.
Verify source/domain/generator/settings consistency with the parent; reject
orphan or mismatched links with explicit reasons. Attack rows belonging to
other clean variants or sources are excluded even when their source was chosen.

Proposed multiplicity policy, requiring plan approval: if more than one row
exists for the same selected parent/allowed attack type, choose the smallest
(row key, id), using the CA1 row tag, and record unused candidates. Do this by
metadata before eligibility; do not substitute another if the winner later
fails. Thus each candidate group has 2 clean rows plus 0–3 attacks, at most
5,000 candidate texts overall. Missing attacks reduce paired attack denominators,
not clean-group eligibility. Record full rows scanned and full EOF completion;
no head-of-file sampling, early stopping or claim of reduced transfer size.

### D. Eligibility and exact identities (selected rows only)

Validate generation as a string decoded strictly from the verified CSV, with
no NUL and control-share <1% using the current ingestion rule (ord<32 excluding
tab/LF/CR/form-feed). Enforce 200,000 decoded code points and the applicable
50,000,000-byte text limit; reject blank/whitespace-only and retained-token
counts below 64. Exactly 64/512 boundaries follow existing scorer policy.
Rows have no filename/extension test (B3). Preserve whitespace, case, zero-width
characters, homoglyphs and Unicode normalization exactly; do not “clean” attacks.
Record all applicable failures with a fixed primary-reason order.

Use only local observer tokenizer assets from the approved model pin in
litmus.config. Check tokenizer.json against
c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539,
record every tokenizer asset/library/config identity, and instantiate a tokenizer
only with local_files_only=True and offline guards. Reuse tokenize_window with
add_special_tokens=False, split_special_tokens=True, right truncation to 512;
record tokens_total, tokens_scored and character range. Never call load_pair,
load model weights, initialize CUDA or import the scoring analyzer to obtain
a tokenizer. Eligibility/window identity uses the real pinned tokenizer; stubs
are for unit tests only.

Proposed hash formats, frozen before the real run:

- raw_text_sha256 = SHA256(exact generation string encoded UTF-8), with no
  normalization or newline rewriting;
- scored_window_sha256 = SHA256(UTF8(compact JSON array of retained integer
  token IDs)), separators=(',', ':'), ensure_ascii=False. Store the sequence
  length and tokenizer identity; this is not a detector score/config hash.

### E. Deduplication and single ordered pair cleanup

Across all eligible candidate rows in **both** splits, index raw-text and
scored-window hashes. If a hash occurs in different source groups, remove
**every** participating row, not a first/preferred/dev representative. Record
the collision channel, hash and affected row/group IDs, including within-split
collisions. Do not move groups across splits to fix leakage.

Then, in this exact single pass:

1. Remove ineligible/colliding rows.
2. Drop groups missing their selected clean human or selected clean machine.
3. Drop attacks whose chosen parent no longer exists, including attacks in a
   dropped group.
4. Assert one human/one clean machine per retained group; every attack references
   that machine in the same source/cell/split; no cross-group raw/window collision
   remains; dev and test source-ID sets are disjoint.

Within-group attack no-ops are retained and counted separately for exact raw
equality and retained-window equality to their clean parent. Attacks changing
only text beyond token 512 can be window no-ops. Do not discard them to improve
later attack metrics. No extra within-group dedup policy is silently added;
other within-group equalities are audit flags. Removal cannot introduce a new
hash collision, so no iterative repair, replacements or quota top-up is needed.

## 5. Manifest, counts and reproducibility contract

Proposed tracked artifacts under `eval/manifests/r1e/`:

- acquisition.json: approved revision/URL, observed transport metadata, bytes,
  advertised and computed digest, license/source references, transfer counters;
- candidates.jsonl: all initially selected group/row IDs, cell assignment, full
  domain-separated keys and split, including candidates later removed;
- retained.jsonl: final IDs, derived human/clean/attack role, parent links,
  source/cell/split, raw/window hashes, eligibility/window metadata and local
  text-blob reference; no copied title/prompt/generation text in Git;
- exclusions.jsonl: row/group identity, stage, all reason codes, primary reason,
  removed-parent linkage and collision members for selected candidates; no
  removed-text dump. Global unselected/out-of-scope populations use reconciled
  counts and the metadata-frame digest, not millions of unselected row records
  committed to Git; critical schema errors retain bounded diagnostic IDs;
- collisions.jsonl and counts.json: collision/no-op details and count tables;
- manifest.json: schema/algorithm versions, N_target, seed/tags/encoding,
  dataset pin/digests, tokenizer/preprocessing identity, source-code byte hashes,
  library versions, all ledger hashes, invariant/reproduction results, final
  split manifests/hashes and calibration-eligibility count only.

Proposed local ignored storage: `data/raid/<revision>/train.csv`, bounded SQLite
indexes and `data/raid/prepared/<run-id>/` UTF-8 text blobs keyed by ID/hash.
Add `.gitignore` protection **before** acquisition. Do not create these paths
or add ignore rules in this planning-only task. A manifest references immutable
content identity, not just machine-specific paths. Preserve raw licensed data
locally; do not commit texts, cache databases or downloaded archives.

Counts must reconcile by stage: scanned rows, schema/metadata rejects, eligible
sources and cells, quota/assigned/shortfall per cell, candidates, eligibility
losses, duplicate rows/groups, dropped pairs/orphan attacks, final groups/rows.
Report candidate and final per-split/domain/generator/attack counts, unique human
counts, decoding/penalty coverage, unknown labels, missing attacks and no-ops.
Distinguish cell-selection shortfalls from post-selection attrition and missing
attack variants. Provide zero-count cells; do not hide empty slices.

Canonical manifests/ledgers: UTF-8, LF, deterministic ordering, sorted object
keys, compact JSON, no machine path/wall-clock time in hashed scientific identity.
Use JSONL final newline and fixed sorting by source_id then role/attack/id.
Acquisition receipt/timestamps and run telemetry have their own hashes, outside
the stable selection identity. Define the manifest identity from a canonical
payload excluding its own digest; record that digest in an envelope/index.
State byte-hash versus semantic/canonical-hash definitions explicitly.

Rerun preparation against the same verified raw file into a separate directory,
without network; compare candidate, exclusion, retained, count and semantic
manifest bytes/hashes. Also test reordered synthetic input to prove selection
does not depend on file order. Real CSV transport hash remains order-sensitive.
Recompute every referenced selected text/window identity and assert all counts
and parent/split invariants. A verifier must fail on altered text, IDs, links,
split, tokenizer assets or ledger hashes. No scoring values belong in any E file.

Final counts are **UNKNOWN**, not zero and not assumed 1,000/300/700. Record
`eligible_development_humans` only after all cleanup. If it is below **200**,
mark 5% calibration ineligible and stop before R1-F; do not expand N, change
the seed, refill, move test groups or lower the requirement. At least 200 is
necessary, not sufficient: R1-F must also enforce score validity and complete
matching execution identity. The 1% calibration remains disabled in R1. No
threshold is created in E even when the count is adequate. R1-F freezes before
any R1-G test scoring, which requires independent confirmation of the freeze.

## 6. Proposed implementation sequence (not authorized by this plan's existence)

Each phase is separately reviewable. File names below are proposed, not present
implementation. Use the existing venv and standard library plus pinned tokenizer
dependencies. Small functions/test cases should form individual implementation
steps; no dataset transformation is run in this planning turn.

| Step | Files / action and reason | Dependency | Risk |
|---|---|---|---|
| E0 | src/litmus/data_prep/keys.py; tests/test_raid_keys.py: implement and prove CA1 encodings/tags before any data use | explicit plan implementation approval | low |
| E1 | scripts/acquire_raid.py; tests/test_raid_acquisition.py; .gitignore: pinned bounded download/receipt and raw-data exclusion; mocked HTTP/range/hash failures first | E0 plus separate acquisition approval | medium |
| E2 | src/litmus/data_prep/schema.py and selection.py; tests/test_raid_selection.py: CSV projection, metadata eligibility, source-unique quotas/ties/split | verified E1 file; schema checks | medium |
| E3 | src/litmus/data_prep/text.py; tests/test_raid_text.py and test_raid_tokenizer.py: tokenizer-only eligibility and exact raw/window identities | frozen E2 candidate ledger | medium |
| E4 | src/litmus/data_prep/cleanup.py; tests/test_raid_cleanup.py: collision removal, pair/attack cleanup, no-op/count invariants | E3 | medium |
| E5 | src/litmus/data_prep/manifest.py; scripts/prepare_raid.py and verify_raid_manifest.py; tests/test_raid_manifest.py: deterministic outputs, tamper checks and repeat run | E4 | medium |
| E6 | docs/interfaces.md, docs/decisions.md and eval/manifests/r1e/: actual identities/counts/shortfalls/limitations; commit preparation/evidence and stop for independent review | E5 verification | low |

Tests before real selection: tiny synthetic CSVs exercising quoting/newlines,
invalid UTF-8, human nulls, out-of-domain rows, multi-generator sources, ties,
exhausted cells, shuffled order, malicious generation access in metadata selector,
64/512/200,000 boundaries, NUL/control ratios, same-window/different-tail
collisions, both-split collision removal, dropped clean parents and no-op attacks.
Repeated IDs/schema ambiguity must fail safely, not silently choose a row.
Use mocked network only for acquisition unit tests; actual acquisition is a
separate explicitly approved operation, never a default-test side effect.

Guard tests must refuse scoring/model constructors, model-weight file reads and
CUDA initialization while a tokenizer-only preparation run succeeds offline.
Follow the repository's marker convention: real-tokenizer tests may be marked
slow, but run that exact tokenizer-only test set separately, not the whole
model/GPU slow suite. Missing local tokenizer assets stop preparation; no fetch.

At E completion run default model-free tests inside/outside the repository,
Ruff, pip check, whitespace checks, scoped Unicode audit, exact tokenizer-only
checks, repeat-run verification and count reconciliation. Record actual commands,
results, not-run checks and resource/selection limitations. Do not report E
complete on a plan, a download alone, expected counts or prior reviewer recaps.

## 7. Approval decisions and stop conditions

Review must approve seed 20261030; the immutable pin/identity preflight; local
MIT-declared evaluation scope; the 13 GB transfer/25 GB task-artifact ceilings
and 30 GB free-space gate; metadata projection interpretation; attack tie policy;
window-hash encoding; and staged E0–E6 implementation scope.

Acquisition permission alone does not authorize pipeline implementation unless
Ryan explicitly approves this plan too. No permission is inferred from N_target,
D3 closure, public availability or saving these documents. Stop for a changed
pin/digest, unknown selected-row schema semantics, budget overrun, unavailable
tokenizer, irreproducible output or failed invariants. Report numerical shortfalls
honestly; never modify the frozen procedure based on downstream scores.
