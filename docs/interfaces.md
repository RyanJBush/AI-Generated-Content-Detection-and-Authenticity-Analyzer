# Interfaces

## Text scorer identity (R1-B1)

Implemented in `src/litmus/scorer/identity.py`; values from `src/litmus/config.py`
and the read-back execution profile (`src/litmus/scorer/loader.py::read_profile`).

### `scoring_config_hash`

`scoring_config_hash = SHA-256( canonical_json(fields) )`, where
`canonical_json` is `json.dumps(fields, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)` encoded as UTF-8. `fields` is a flat object with exactly
these keys:

**Addendum A4 fields and preprocessing policy** (static, `litmus.config`):
`scorer_version`, `formula_id`, `observer_repo`, `observer_commit`,
`performer_repo`, `performer_commit`, `tokenizer_json_sha256` (computed from
the local file at load and required to equal the pinned value),
`add_special_tokens`, `split_special_tokens`, `truncation_side`, `max_tokens`,
`min_tokens`, `weight_dtype`, `reduction_dtype`, `score_direction`,
`preprocessing_version`.

**Numerical execution profile** (read back at runtime, never the requested value):
`device_type`, `gpu_name`, `nvidia_driver_version` (via NVML, no subprocess),
`cuda_runtime` (`torch.version.cuda`), `torch_version`, `transformers_version`,
`tokenizers_version`, `attn_implementation` (from both loaded model configs),
`batch_size`, `matmul_allow_tf32`, `cudnn_allow_tf32`,
`float32_matmul_precision`, `deterministic_algorithms`,
`cublas_workspace_config`, `weight_dtype` (from the loaded parameters),
`reduction_dtype`, `os_family`, `cuda_initialized_before_settings` (whether
`torch.cuda.is_initialized()` was already true when the numerical settings were
applied; see the initialization-order rule).
The read-back `weight_dtype` / `reduction_dtype` must equal the configured
values, otherwise hashing is refused. On CPU, GPU-only fields are
`"not_applicable"`.

**Source identity**: `source_files` (the list below) and `source_sha256`.

### Source file list and `source_sha256`

```
src/litmus/config.py
src/litmus/ingestion.py
src/litmus/scorer/analyzer.py
src/litmus/scorer/binoculars.py
src/litmus/scorer/identity.py
src/litmus/scorer/loader.py
src/litmus/scorer/tokenize.py
```

`analyzer.py` and `identity.py` were added in the R1-B1 corrections: they decide
completeness, the reported result and the hash itself.

For each path in sorted order: `entry = path + "\n" + sha256(file bytes with
CRLF replaced by LF)`. `source_sha256 = SHA-256( UTF-8( "\n".join(entries) ) )`.
CRLF→LF normalization applies only to these files. The list itself is also a
hash field (`source_files`).

### Required-field schema and completeness (Corrections A CA2; R1-B1 corrections)

Implemented as `PROFILE_SCHEMA` / `profile_failures()` in
`src/litmus/scorer/loader.py`. The profile must have exactly these keys:

| Field | Permitted value on `cuda` | On `cpu` |
|---|---|---|
| `device_type` | `"cuda"` or `"cpu"` | same |
| `gpu_name` | non-empty string | `"not_applicable"` |
| `nvidia_driver_version` | string matching `\d+(\.\d+)+` (e.g. `572.60`) | `"not_applicable"` |
| `cuda_runtime` | string matching `\d+\.\d+` (e.g. `12.4`) | `"not_applicable"` |
| `cublas_workspace_config` | `":4096:8"` | `"not_applicable"` |
| `torch_version`, `transformers_version`, `tokenizers_version` | string matching `\d+(\.\d+)+` plus an optional local/pre-release suffix (e.g. `2.6.0+cu124`) | same |
| `attn_implementation` | `"eager"` | same |
| `batch_size` | int `1` | same |
| `matmul_allow_tf32`, `cudnn_allow_tf32` | bool `false` | same |
| `float32_matmul_precision` | `"highest"` | same |
| `deterministic_algorithms` | a bool | same |
| `weight_dtype`, `reduction_dtype` | `"float32"` | same |
| `os_family` | `"Windows"`, `"Linux"` or `"Darwin"` | same |
| `cuda_initialized_before_settings` | bool `false` | same |

`"not_applicable"` is permitted only for the four GPU-specific fields, and only on
CPU. The profile is **incomplete** if any of these holds: it is empty; a key is
missing; an extra key is present; a value is `None`, an empty or blank string,
`"unavailable"` or `"unknown"`; a value is outside its permitted set; or a
model setting (`attn_implementation`, `weight_dtype`) differs from the value
read from either loaded model.

An incomplete profile gives `inconclusive` with reason
`execution_profile_incomplete`, and `details.execution_profile_failures` maps
each failing field to its reason. It never matches a calibration, even one
carrying the same hash. If the profile cannot be hashed (for example, a missing
key), `scoring_config_hash` is `null`.

### Initialization-order rule

`configure_numerics(device_type)` is the one function that applies every
numerical setting: `CUBLAS_WORKSPACE_CONFIG` (on CUDA with deterministic
algorithms), both TF32 flags, float32 matmul precision, and deterministic
algorithms. It must run **before** any CUDA or cuBLAS initialization. It records
`torch.cuda.is_initialized()` as observed by the first call in the process for
that device type. A later call cannot overwrite this record.

Reading back the environment variable is not proof that it took effect, because
cuBLAS reads it once, when cuBLAS initializes. If CUDA was already initialized
when the settings were applied, or if no configuration ran (order cannot be
established), then `cuda_initialized_before_settings` is not `false`. The
profile is then incomplete, with the additional reason
`cuda_initialized_before_settings`. There is no workaround, and analysis never
starts subprocesses.

**Re-read before scoring:** immediately before each scoring call, the analyzer
re-reads the effective settings: both TF32 flags, matmul precision, the
deterministic flag, `cublas_workspace_config`, and each model's attention
implementation and weight dtype. It compares them with the profile that was
hashed, and never re-applies them. On any difference the result is
`inconclusive` with reason `execution_profile_changed` and no `raw_score`, and
`details.execution_profile_changes` lists each field as `{profile, effective}`.

### Calibration matching

Strict: a calibration file in `calibrations/*.json` applies only if its
`scoring_config_hash` equals the runtime hash exactly. In R1-B1 no calibration
files exist, every run is uncalibrated (`inconclusive`, reason
`no calibration for this configuration`), and CPU runs are always uncalibrated.
Threshold application is not implemented (R1-F); a matching file would yield
`calibration_application_not_implemented`.

### OriginEvidence emitted by the text analyzer (`method_id = "binoculars"`)

`raw_score = B`, `score_direction = "lower_means_more_machine"`,
`calibration = null`, `result = "inconclusive"`, plus `details`:
`scored_window` (`tokens_total`, `tokens_scored`, `truncated`,
`scored_char_range` in code points), `nll_performer`, `xent`, `n_input_tokens`,
`n_target_tokens`, `tokenizer_vocab_size`, `model_output_dim`,
`scoring_config_hash`, `scoring_config` (the hashed fields, which include the
execution profile), `execution_profile_complete`, `execution_profile_failures`.

## Text quality observations (R1-C2)

Opt-in, model-free observations of what a text segment contains. **Quality
observations do not establish AI origin and never affect origin results.**

### `--quality {off,on}`

- `off` (the default): no observer is constructed or run. The report is
  byte-identical to the report without quality support: every segment has
  `"quality": []` and `limitations` is unchanged (checked against the golden
  files; `--quality off` output equals the output with the flag omitted).
- `on`: the four observers are constructed (lexicons loaded and validated)
  before analysis starts. Origin evidence is computed first; then each **text**
  segment gets four observations, in the order below, from its decoded text
  alone. Image segments keep `"quality": []`. The report's `limitations` gains
  the quality limitations (`report.QUALITY_REPORT_LIMITATIONS`), including
  "quality observations do not establish AI origin and never affect origin
  results", "quality lexicons are English-oriented and provisional (v1)" and
  "quality word counts assume space-separated scripts; ...".

### Observer IDs (`observer_version = "1"`)

| `observer_id` | What is counted |
|---|---|
| `stock_phrases` | matches of the packaged `stock_phrases` lexicon |
| `hedges` | matches of the packaged `hedges` lexicon |
| `repeated_word_3grams` | every occurrence of a word 3-gram whose casefolded key occurs at least twice (consecutive words of the word index; crosses punctuation and line breaks; no stop-word filtering) |
| `claim_phrases_to_inspect` | matches of the packaged `claim_phrases_to_inspect` lexicon |

Lexicon matching is case-insensitive on the original text, leftmost-longest
and non-overlapping, with word-boundary lookarounds (R1-C1 entry compiler).

### Record fields

- `count`: exact number of matches (never capped).
- `status`: `observed` if `count > 0`, else `none_found`; `error` on failure.
- `rate_per_100_words`: `count / words * 100`, where `words` is the word-index
  count of the segment text; `null` when the text has zero words.
- `spans`: `[start, end)` code-point offsets into the decoded segment text, in
  order; at most **1,000** (the span cap) are listed.

### `notes` format

Fixed `key=value` strings, in this order:

1. `observer_version=1`
2. lexicon observers only: `lexicon_name=<name>`, `lexicon_version=<n>`,
   `lexicon_sha256=<sha256 of the packaged file bytes>`
3. `spans_truncated=true|false` (true when `count` exceeds 1,000), then
   `spans_reported=<number of spans listed>`
4. `claim_phrases_to_inspect` only:
   `label=phrase to inspect; not evidence that a claim is unsupported`

### Error behavior

Each observer runs in its own `try/except`. An exception yields that
observer's record with `status = "error"`, `count = null`,
`rate_per_100_words = null`, `spans = []` and notes
`["observer_version=1", "error=<exception class name>"]`; the other observers'
records and the origin evidence are unchanged, and the CLI still exits 0. A
packaged lexicon that fails validation gives the same error record with the
note `lexicon_invalid=<reason>` instead of `error=...`.

Lexicon loading happens when the observers are constructed (before analysis),
separately for each lexicon observer. A `LexiconError` gives that observer
`lexicon_invalid=<reason>` (a resource missing at the file read is reported as
`lexicon_invalid=lexicon '<name>' is not packaged`). An `OSError` or any
subclass (for example `PermissionError`) gives that observer
`error=<exception class name>`. In both cases the other observers, origin
evidence and the report are unaffected, and the CLI exits 0. Any other
exception during lexicon loading is not caught: it propagates out of the CLI
(traceback, exit 1) before analysis starts.

## C2PA pipeline (D2) and opt-in image reports (D3)

`litmus.c2pa.pipeline.analyze_c2pa(data, mime, *, config, policy=PRODUCTION_POLICY,
worker=None, deadline=120.0, read=read_store, supported=None)` is an internal
testable pipeline. Callers supply bytes already accepted by image ingestion;
it does not reopen a path. D3 wraps it with `analyzer.analyze_image` and connects
it to accepted image segments in `report.py` only with `--c2pa on`.
Default image reports retain `image_origin_placeholder` and
`c2pa_analyzer_disabled_in_r0`. Omitted and explicit `--c2pa off` produce the
same bytes as the existing goldens; no native SDK or worker is initialized.
Text-only and rejected inputs do not initialize the image analyzer even with on.

`reader.read_store` returns `ReadOutcome(kind, store, reasons, detail,
settings_applied, read_seconds)`.
Kinds are `store`, `no_credentials`, `remote_reference_only`, or `error`.
Settings rejection gives `c2pa_settings_rejected`; other exceptions reach
rule 2. The worker owns settings, context, input stream and reader, and closes
them before finishing. Cleanup of a handle whose SDK constructor fails is
the SDK's responsibility; successfully returned objects are closed explicitly.
Supported MIME types are cached once per process.

Settings come from the D1 builder, `Settings.from_dict`: remote manifest and
OCSP fetch off, allowed network hosts empty, identity assertion decoding off,
trust verification on. `production_config()` loads the packaged, versioned,
empty PEM list and refuses a nonempty list. `test_anchor_config(pems)` is an
explicit separate settings path. It does not change Litmus policy by itself.
Production `signer_trust` is always `unknown`, including when the SDK reports
`signingCredential.trusted`. SDK observations are diagnostics, not policy.
Only tests define `TestOnlyPolicy`; trusted outcomes require explicitly
passing both that policy and test-anchor settings. No source module imports
test anchors or the test policy.

### Normalized store and attribution (`mapping_version = "1"`)

`map_store(store, policy=PRODUCTION_POLICY)` returns `MappedStore`:

- `validation_state`: raw overall SDK state, diagnostic only;
- `active_label`, `policy`, `mapping_version`;
- `records`: active first, then referenced ingredients, then other manifests;
- `ingredient_labels`: only manifests referenced by the active claim;
  `ingredients` selects these records, excluding unrelated manifests;
- `status_entries`: original entry, list, attributed label and originating
  results location (preserves assertion URLs and explanations);
- `unattributed`: code, list, URL and origin for entries without a known label;
- `unmapped_status_codes`: code, list, URL, label and origin for unknown codes.

Each `ManifestRecord` carries `manifest_label`, `is_active`, ingredient
`relationship` and `title`, `integrity`, `signature`, `timestamp`,
`signing_time_basis`, `signer_trust`, `declared_ai_use`,
`sdk_trust_observation`, `sources` and `notes`.

The manifest named in each absolute `self#jumbf=/c2pa/<label>/...` URL owns
the status, regardless of the results list containing it. A relative JUMBF
URL uses the enclosing manifest's label where known. Missing URLs and unknown
labels are unattributed and make active integrity/signature `not_checked`
unless already `invalid`. This also applies to stored ingredient results.
Current ingredient-delta trust codes supersede stored ingredient trust codes.
Active `assertion.action.ingredientMismatch` invalidates active integrity;
the same code on an ingredient affects that ingredient only. Ingredient
binding matches cannot establish integrity of the analyzed image. Ingredient
integrity stays `not_checked` unless a negative code makes it `invalid`.

### Status mapping and evidence limits

Positive evidence counts only in `success`. Integrity needs a hard-binding
match; signature needs both `claimSignature.validated` and
`claimSignature.insideValidity`. Hashed-URI and ingredient validation alone
are insufficient. Invalid beats incomplete. Every unknown code, including
an unknown timestamp code, makes both integrity and signature `not_checked`
unless already invalid, as required by plan section c strictness rule 2.

All 45 codes below are exercised by explicitly **constructed** stores in
`tests/fixtures/c2pa/constructed/mapping_rows.json`. The nine codes marked
**real** were also observed in D1 captures. All other codes are demonstrated
only by constructed injection; SDK emission remains undemonstrated for them.
There are no rows without mapping-test coverage. Constructed coverage is not
evidence that the pinned SDK emits a code or assigns it to a particular list.

| Codes | Effect | Real SDK observations |
|---|---|---|
| `assertion.dataHash.match`, `assertion.boxesHash.match`, `assertion.bmffHash.match` | hard-binding evidence | dataHash only |
| `assertion.hashedURI.match` | reference evidence, insufficient alone | real |
| `assertion.dataHash.mismatch`, `assertion.boxesHash.mismatch`, `assertion.bmffHash.mismatch` | integrity invalid | dataHash only |
| `assertion.hashedURI.mismatch`, `assertion.missing`, `claim.hardBindings.missing`, `assertion.action.ingredientMismatch` | integrity invalid | constructed only |
| `ingredient.manifest.validated` | ingredient evidence, insufficient alone | real |
| `ingredient.manifest.mismatch`, `ingredient.manifest.missing` | integrity invalid on attributed manifest | constructed only |
| `ingredient.unknownProvenance` | recorded only | constructed only |
| `claimSignature.validated`, `claimSignature.insideValidity` | signature evidence, both required | both real |
| `claimSignature.mismatch`, `claimSignature.missing`, `claimSignature.outsideValidity` | signature invalid | constructed only |
| `signingCredential.invalid`, `signingCredential.expired`, `signingCredential.revoked`, `signingCredential.ocsp.revoked` | signature invalid | constructed only |
| `ingredient.claimSignature.validated`, `ingredient.claimSignature.mismatch` | evidence (insufficient alone), invalid respectively | constructed only |
| `signingCredential.ocsp.skipped`, `signingCredential.ocsp.notRevoked`, `signingCredential.ocsp.inaccessible` | recorded only | skipped only |
| `signingCredential.trusted`, `signingCredential.untrusted` | SDK trust diagnostic; production policy remains unknown | both real |
| `timeStamp.trusted`, `timeStamp.validated` | both required for timestamp trusted_validated | constructed only |
| `timeStamp.malformed`, `timeStamp.mismatch`, `timeStamp.untrusted`, `timeStamp.outsideValidity` | timestamp ignored; no signature invalidation by themselves | constructed only |
| `general.error`, `algorithm.unsupported`, `claim.missing`, `claim.multiple`, `manifest.missing`, `manifest.inaccessible`, `manifest.multipleParents`, `assertion.cbor.invalid` | integrity and signature not_checked unless invalid | constructed only |

`claimSignature.outsideValidity` and `signingCredential.revoked` were absent
from the D1 binary-name scan. Their constructed treatment is conservative
Litmus policy, not a claim of SDK support.

Timestamp states are `absent`, `ignored`, `not_checked`, or
`trusted_validated`. They are independent of claim-signature state. A lone
timestamp success code is incomplete. `insideValidity` alone never proves a
verified signing time. `signing_time_basis` is `trusted_timestamp` only for
the paired timestamp successes; with absent/ignored timestamps and a
credential validity code it is `current_time_check`, otherwise `unknown`.
This is a policy interpretation of codes, not an independent clock or TSA
verification. All real R1 fixtures have no TSA and map to timestamp `absent`.
No real timestamp validation is demonstrated. The reviewer supplied the
[C2PA 2.5 section 14.8 citation](https://spec.c2pa.org/specifications/specifications/2.5/specs/C2PA_Specification.html#_validate_the_time_stamp).
The builder did not independently fetch or verify the specification text;
the timestamp split follows Ryan's correction 2 and the reviewed D2 policy.

AI use is declared only in `c2pa.actions` or `c2pa.actions.v2` for these exact
`digitalSourceType` values:

- `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia`
- `http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia`

Near misses and other source types are recorded in notes and never declare AI
use. Unrelated assertions cannot declare it.

### Ordered result rules

`evaluate_rules(RuleInput)` is pure and returns
`RuleOutcome(rule, result, label, reasons, limitations, details)`.
First match wins; active fields govern except rule 9.

| Rule | Condition | Result / label |
|---|---|---|
| 1 | unsupported format; reader is not called | not_supported / c2pa_format_unsupported |
| 2 | read/settings/mapping error, deadline or busy worker | error / c2pa_error |
| 3 | no store | inconclusive / no_credentials |
| 4 | remote reference only, not fetched | inconclusive / remote_reference_only |
| 5 | integrity or signature invalid | inconclusive / validation_failed |
| 6 | integrity or signature not_checked | inconclusive / validation_incomplete |
| 7 | active declares, trusted under explicit test policy | supports_ai / trusted_provenance_ai_declared |
| 8 | active declares, untrusted or unknown | inconclusive / untrusted_signed_ai_declaration |
| 9 | only referenced ingredient declares | inconclusive / ingredient_ai_declaration |
| 10 | no declaration | no_signal / manifest_no_ai_declaration |

Rule 9 details identify declaring ingredients by label, relationship, title
and their own integrity/signature/timestamp/trust states. Their states never
upgrade the result. Validation failures and incomplete validation precede
declarations. Every outcome carries the empty-production-trust and
provenance-only limitations. No credentials and no declaration are not
evidence of human origin.

### Remote adapter and deadline

For c2pa-python **0.38.0 / SDK 0.91.0 only**, a `C2paError` beginning exactly
`Remote: must fetch remote manifests from url ` maps to rule 4 when
`verify.remote_manifest_fetch` is explicitly false. This fragile message
adapter is justified by the captured error and both Builder/XMP pipeline
tests. Version drift, a different prefix or enabled fetch fails closed to
rule 2. It is never treated as no credentials.

The paired tests observe **zero attempted connections with passing controls**
for both remote fixtures: production settings give zero loopback-trap
connections; fetch enabled with only the trap host allowed gives one GET
and a deliberate 404. This covers those fixtures/settings/destination only.
Network isolation was not run; no Docker image was pulled.

`get_worker()` lazily creates one dedicated daemon thread per process.
There is at most one outstanding task and no queue. A 120-second deadline
returns rule 2 / `c2pa_timeout`; native work is not cancelled. While any task
still runs, new requests return rule 2 / `c2pa_worker_busy` immediately.
The worker is never replaced while busy. When the task finishes, inputs and
abandoned outputs/exception tracebacks are released before idle is published;
subsequent requests can use the same thread. Explicit cleanup runs on the
worker after both normal and timed-out requests, including error exits.
Short injected deadlines and blocked stubs test these semantics; no real
120-second native hang was induced. Daemon shutdown cannot guarantee native
cleanup if the process exits while work is still running.

### D3 report contract and errors

`build_report` and `run_analysis` accept keyword-only `c2pa_enabled=False`.
The CLI exposes `--c2pa {off,on}` (default off). With on, only accepted image
segments replace the placeholder; text origin/quality and scoring hashes remain
unchanged. C2PA is run from `Ingested.raw`/`mime`, without another path read.

`OriginEvidence` uses `method_id=c2pa_provenance`, `method_version=1`, and null
raw_score, score_direction and calibration. The D2 engine supplies result/reasons.
The schema identifier remains `litmus-report/r0`; its existing provenance/details
dictionaries support these additive opt-in values without changing default bytes.

`provenance` fields:

- `manifest_present`: embedded, none or remote_reference_only when established;
  null when presence could not be established (for example timeout or busy);
- `active`: normalized active record or null; `ingredients`: referenced records;
- `mapping_version`, `policy` (production);
- `trust_list`: name, version, SHA-256 of exact packaged bytes, anchor_count;
- `library_versions`: c2pa_python and sdk;
- `settings`: requested offline/trust configuration; confirmed application is
  tracked separately in details;
- `unsigned_metadata`: the minimal independent summary below.

`details` includes rule number, diagnostic validation_state, status_entries,
unmapped_status_codes, unattributed, other_manifests (unreferenced diagnostic
records), declaring_ingredients where applicable, read_kind, read_detail,
settings_applied, availability_notes and timings. Missing validation data is
null/empty with an availability note; it is never inferred from rule outcome.

`settings_applied=true` confirms successful settings construction and Context
creation on the completed read path, not network-policy effect. False means
settings were rejected. Null means unconfirmed (for example a busy request,
timeout or unexpected exception); settings then describes intent only.
`timings` uses seconds: read_seconds is worker read duration including settings
and cleanup when returned; read_response_seconds is pipeline wall time;
response_seconds is adapter wall time through metadata summary. Unknown read
durations stay null, including after timeout: later native completion never
retroactively modifies an emitted report.

Every evidence record and enabled image report carries empty-trust,
provenance-only, absence-not-human, offline remote-fetch, SDK-observation/policy
and constructed-timestamp limitations, plus applicable D2 rule/timeout limits.
Report-level placeholder wording is replaced only when image C2PA ran.

The activation prerequisite is the explicit reviewed-offline-evidence constant
in `c2pa/analyzer.py`, backed by review through 0c6fa08. It triggers no network
probe or test suite at runtime. Unavailable evidence, invalid trust resources,
SDK import failure or different library versions raise `C2paUnavailable`.
The CLI exits 1 with stderr, no report, and no output-file write. Settings/read/
mapping/discovery failures after initialization instead yield rule-2 error
evidence; timeout/busy reasons are preserved. A valid emitted report exits 0
even when an analyzer result is error. Argument errors exit 2. No enabled image
failure silently returns the disabled placeholder.

### Unsigned metadata

`unsigned_metadata.label` is `unverifiable; editable; not evidence`.
Its status is examined, partial or unavailable; notes explain failures.
`exif` contains status (present/absent/unavailable), tag_count (null if unknown)
and fields. Only Software, Make, Model and DateTime are included, converted to
text and truncated to 256 code points. No timestamp validation is inferred.
`xmp` contains status and byte_length, zero for absent and null if unavailable.
Presence/absence is limited to what Pillow exposes in its info dictionary; no
XMP parser or search for additional packets is used. EXIF/XMP failures are
isolated independently. Metadata affects neither result/reasons nor signed
declarations, trust or validation. It is inspected from in-memory bytes only.

### Installed-wheel verification

`scripts/verify_wheel_c2pa.py --output eval/results/r1d3_wheel_check.json` runs
with the existing .venv interpreter. It builds with --no-index --no-deps
--no-build-isolation, installs only Litmus into a fresh temporary --target,
then launches the same interpreter with -I from outside the repository.
Existing pinned runtime dependencies remain available in .venv site-packages;
no dependencies are installed or downloaded. The fresh target is first on
sys.path. Every loaded Litmus module must have its file under that target;
runtime c2pa/Pillow must resolve inside the existing venv. This detects an
editable checkout masking a packaging omission. The check verifies resource
hash/emptiness, absence of test anchors/keys, enabled JPEG/PNG/WebP analysis,
default golden equality and no model imports. pip freeze --all before/after
must match. Temporary artifacts are left for review and their location recorded.
