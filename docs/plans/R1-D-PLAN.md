# R1-D plan — C2PA image provenance

**Status: D1 and D2 CLOSED; D3 APPROVED by Ryan on 2026-10-30; implementation submitted for independent review.** The approved scope is `R1-D3-BUILD-PROMPT.md`. Sections p–r supersede earlier planning statements; section r reconciles current implementation and evidence.

Sections a–o retain original design discussion and feasibility questions for
traceability. Remaining PROPOSED/UNVERIFIED wording there is historical; use
the reviewed D1/D2 evidence, current interface contract and section r for
resolved questions. D3 approval does not authorize later checkpoints.

- **Drafted** 2026-10-30 on top of `4c3f42c` (R1-C2 closure record).
- **Governing documents, in precedence order:**
  1. R1-PLAN-CORRECTIONS-A.md;
  2. R1-PLAN.md (§1.4, §2 row R1-D);
  3. SPEC-v0.3-ADDENDUM-B.md (B4);
  4. SPEC-v0.3-ADDENDUM-A.md (A1, A2);
  5. SPEC.md (§4.2, §6.2, §7, §8.2).

  Corrections A (CA1–CA3) has no C2PA content, so R1-PLAN.md §1.4 is the highest governing text for this plan.
- **Out of scope:** RAID acquisition, calibration, image detection, UI work and new packages.
- **Status labels:**
  - **VERIFIED:** checked on 2026-10-30 against the installed library in `.venv`. The library is c2pa-python 0.38.0 (dist-info `Version: 0.38.0`, `License: MIT OR Apache-2.0`), native SDK 0.91.0 (`c2pa.sdk_version()` printed `0.91.0`). Each fact cites a file and function.
  - **PRESENCE ONLY:** the string occurs in the native library binary `c2pa/libs/c2pa_c.dll`. This does not show the library emits it, or under what conditions.
  - **UNVERIFIED:** not checked. D1 must settle it.
- **Recommendations** are marked RECOMMENDED and are for Ryan to accept or change.

---

## a) Scope

- **Formats: embedded C2PA manifest stores in JPEG, PNG and WebP.**
  - VERIFIED: `Reader.get_supported_mime_types()` (`c2pa/c2pa.py`, `class Reader`, classmethod `get_supported_mime_types`, backed by native `c2pa_reader_supported_mime_types`) returned 96 entries on 2026-10-30. They include `image/jpeg`, `image/png` and `image/webp` (also `image/x-webp`).
  - Rule 1 (`not_supported` / `c2pa_format_unsupported`) applies when the ingested MIME type is not in that list at run time. The list is read once per process.
  - In R1, ingestion only accepts JPEG/PNG/WebP images (`src/litmus/ingestion.py`, `ingest`, by file signature). Rule 1 is therefore a guard for library version changes; it is not a path that expected input reaches.
- **Input: bytes already ingested.**
  - The analyzer reads `Ingested.raw`, the bytes read once in `ingest`, through an in-memory stream (`io.BytesIO`). It never opens the path again.
  - It passes the ingested MIME type as the format: `Reader(format, stream, context=...)`, per `c2pa/c2pa.py`, `Reader.__init__`.
  - VERIFIED, from the `Reader.__init__` docstring: when the given format disagrees with the container the library detects, the library ignores the format. When it detects no container, it treats the asset as a sidecar.
  - The analyzer therefore runs only on image segments that ingestion accepted. Those already passed the signature check, the 50 MB size limit, the 50-megapixel header check and a full decode (`ingest`; SPEC §6.2).
- **Limits applied first.** The analyzer is never called for inputs that ingestion rejected. Rejected inputs keep their `not_supported` / `error` ingestion result.
- **Per-analyzer response deadline: 120 s per segment (SPEC §6.2).** D2 implements a single dedicated worker with event-based response waiting. The original per-call `join(timeout)` proposal was superseded by section p Correction 3.
  - On expiry, the segment gets rule 2 (`error`), with reason `c2pa_timeout` in `reasons` and the label `c2pa_error`.
  - **Superseded by §p Correction 3.** The timeout is a response deadline, not cancellation: one dedicated worker per process, at most one outstanding task, and `c2pa_worker_busy` while a timed-out task still runs.
  - **Limitation:** a native call cannot be cancelled. A timed-out task keeps running on the worker until it finishes. This limitation is stated in the report's limitations whenever a timeout occurs.
  - The timeout value is a constant, and tests can inject a smaller one.

## b) Manifest model (SPEC §8.2)

- **Active vs ingredient manifests.**
  - The active manifest is the one the store's `active_manifest` key names.
    - VERIFIED: `Reader.get_active_manifest()` (`c2pa/c2pa.py`) reads `data["active_manifest"]` and returns `data["manifests"][id]`. It raises `KeyError` if either key is missing or the id is absent.
  - Ingredient manifests are manifests referenced by the active manifest's `ingredients` entries.
    - VERIFIED: `Reader.get_manifest(label)` returns `data["manifests"][label]`.
    - D1 captures demonstrate the ingredient `active_manifest` link; D2 uses it.
- **Per declaration**, every manifest reported carries:
  - `manifest_label`;
  - `is_active`;
  - for ingredients, `relationship` (for example `parentOf` / `componentOf`, as the library reports it) and the ingredient `title`.
- **Per-manifest fields** (none implies another):

| Field | Values | Note |
|---|---|---|
| `integrity` | `valid` / `invalid` / `not_checked` | Ingredient binding matches cannot establish validity for the analyzed asset; attributed negative codes may make an ingredient invalid. |
| `signature` | `valid` / `invalid` / `not_checked` | Claim-signature/credential validation; verified signing time is a separate timestamp state. |
| `signer_trust` | `trusted` / `untrusted` / `unknown` | `unknown` when no trust anchors are configured. That is always the case in production in R1 (§h, §i). |
| `declared_ai_use` | `declared` / `not_declared` | `declared` when a `c2pa.actions` (or `c2pa.actions.v2`) assertion contains an action whose `digitalSourceType` is exactly one of the IPTC URIs for `trainedAlgorithmicMedia` or `compositeWithTrainedAlgorithmicMedia` (SPEC §17 [9]). See the note below the table. |

  Notes on `declared_ai_use`:
  - The accepted URI forms are a fixed list in code. A near-miss is recorded in `details` but does not count.
  - PRESENCE ONLY: `trainedAlgorithmicMedia`, `compositeWithTrainedAlgorithmicMedia`, `digitalSourceType` and `c2pa.actions` occur in `c2pa_c.dll`.
  - VERIFIED: `C2paDigitalSourceType` in `c2pa/c2pa.py` has members `TRAINED_ALGORITHMIC_MEDIA` and `COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA`. They are used for Builder intent (`Builder.set_intent`).
  - Litmus reads declarations from the manifest JSON, not from this enum.

## c) Mapping library output to fields

**Source of data.** For each read, the analyzer uses only these calls:
- `Reader.json()`: the manifest store JSON (`c2pa/c2pa.py`, `Reader.json`, native `c2pa_reader_json`).
- `Reader.get_validation_state()`: reads `validation_state` from that JSON.
- `Reader.get_validation_results()`: reads `validation_results` from that JSON.

**Structure of the results (all labels below are PRESENCE ONLY in `c2pa_c.dll`).**
- `validation_results` is expected to contain `activeManifest` with `success` / `informational` / `failure` code lists, plus `ingredientDeltas` for ingredients.
- Each entry is expected to carry a status `code`.
- D1 committed real output pins this JSON shape; D2 normalizes it by manifest/assertion context.

**Validation state is not used to set fields.** `validation_state` (VERIFIED accessor `Reader.get_validation_state`; values UNVERIFIED) is recorded in `details` only. Fields come from individual status codes, because one overall state cannot separate integrity from signature from trust.

**Proposed mapping (active manifest).** Status code names below are from the C2PA specification. Each one is PRESENCE ONLY in `c2pa_c.dll` unless marked "absent". Whether, when and in which list the library emits each code is UNVERIFIED until D1/D2 fixtures show it.

| Status code | List | Effect |
|---|---|---|
| `assertion.dataHash.match`, `assertion.boxesHash.match`, `assertion.bmffHash.match` | success | integrity evidence (hard binding matches) |
| `assertion.dataHash.mismatch`, `assertion.boxesHash.mismatch`, `assertion.bmffHash.mismatch` | failure | `integrity = invalid` |
| `claim.hardBindings.missing` | failure | `integrity = invalid` |
| `assertion.hashedURI.match` | success | assertion-reference evidence (recorded) |
| `assertion.hashedURI.mismatch`, `assertion.missing` | failure | `integrity = invalid` (the claim no longer matches its assertions) |
| `claimSignature.validated` | success | signature evidence |
| `claimSignature.insideValidity` | success | signature evidence (certificate valid at signing time) |
| `claimSignature.mismatch`, `claimSignature.missing` | failure | `signature = invalid` |
| `signingCredential.invalid`, `signingCredential.expired` | failure | `signature = invalid` |
| `signingCredential.trusted` | success | `signer_trust = trusted` only if the configured anchor list is non-empty (tests only in R1) |
| `signingCredential.untrusted` | failure or informational | `signer_trust = untrusted` if anchors are configured; `unknown` if the list is empty |
| `timeStamp.validated`, `timeStamp.trusted`, `timeStamp.untrusted`, `signingCredential.ocsp.skipped`, `signingCredential.ocsp.notRevoked` | any | no field effect; recorded in `details` |
| `signingCredential.ocsp.revoked` | failure | `signature = invalid` |
| `timeStamp.mismatch`, `timeStamp.outsideValidity` | failure | **superseded by §p Correction 2:** recorded as a timestamp state, separate from `signature`; not by itself `signature = invalid` |
| `signingCredential.ocsp.inaccessible` | any | no field effect; recorded. It is expected only if OCSP were attempted, which settings forbid (§f). |
| `general.error`, `algorithm.unsupported`, `claim.missing`, `claim.multiple`, `manifest.missing`, `manifest.inaccessible`, `manifest.multipleParents`, `assertion.cbor.invalid` | failure | `integrity = not_checked` and `signature = not_checked`, unless already `invalid` |
| `assertion.action.ingredientMismatch` | failure | **context-aware (§p Correction 1):** on the active claim, it affects the active manifest (`integrity = invalid`, pending D2 confirmation); on an ingredient's claim, it affects that ingredient's record |
| `ingredient.*` codes | failure/any | applied to the manifest the code belongs to (§p Correction 1); recorded |

Absent from the D1 binary-name scan: `claimSignature.outsideValidity`, `signingCredential.revoked`, `algorithm.deprecated`. The first two have conservative constructed-only D2 mappings; this does not establish SDK emission. `algorithm.deprecated` remains unmapped.

**Strictness rules (proposed):**
1. **Positive evidence required.**
   - `integrity = valid` requires at least one hard-binding `*.match` code and no `invalid` code.
   - `signature = valid` requires `claimSignature.validated` and `claimSignature.insideValidity`, and no `invalid` code. Per §p Correction 2, `insideValidity` does not by itself prove a verified signing time; signing-time verification is reported separately.
   - Otherwise the field is `not_checked`.
2. **Unmapped or unrecognized codes.** Any status code on the active manifest that is not in the table above sets both `integrity` and `signature` to `not_checked`, unless already `invalid`. This leads to rule 6, `inconclusive` / `validation_incomplete`. The code is listed in `details.unmapped_status_codes`.
3. **Invalid wins.** `invalid` beats `not_checked`, matching rule order (5 before 6).
4. **Ingredients.**
   - Ingredient `signature` and `signer_trust` come from the codes reported for that ingredient (`ingredientDeltas` or the ingredient's own `validation_results`; UNVERIFIED shape).
   - Ingredient binding matches leave `integrity` not_checked; attributed negative codes may make it invalid (see sections b and r).
   - Ingredient states are reported but never change `result` beyond rule 9 (A2 precedence note).
5. **Mapping changes need a fixture.** The table is versioned in code (`mapping_version`), and that version is reported. Changing an entry requires a fixture or committed library output demonstrating the code.

**Verification.** D2 checks every mapping row against committed library output: real fixtures where they produce the code, otherwise constructed output labeled `constructed` (§j). Rows that no output in R1-D demonstrates are listed as such in D2's report and in `docs/interfaces.md`.

## d) Result rules (Addendum A2, verbatim; first match wins)

> Rules are evaluated **in order; the first matching rule determines `result`**. This makes outcomes mutually exclusive.
>
> | # | Condition (active manifest unless stated) | `result` | Label |
> |---|---|---|---|
> | 1 | Format not supported by the pinned c2pa library | `not_supported` | `c2pa_format_unsupported` |
> | 2 | Library error or timeout | `error` | `c2pa_error` |
> | 3 | No manifest store found | `inconclusive` | `no_credentials` |
> | 4 | Only a remote manifest reference (not fetched, A1) | `inconclusive` | `remote_reference_only` |
> | 5 | `integrity = invalid` **or** `signature = invalid` | `inconclusive` | `validation_failed` — declarations shown, not used as evidence |
> | 6 | `integrity = not_checked` **or** `signature = not_checked` | `inconclusive` | `validation_incomplete` |
> | 7 | `declared_ai_use = declared` and `signer_trust = trusted` | `supports_ai` | `trusted_provenance_ai_declared` |
> | 8 | `declared_ai_use = declared` and `signer_trust ∈ {untrusted, unknown}` | `inconclusive` | `untrusted_signed_ai_declaration` |
> | 9 | Active not declared; ≥1 ingredient manifest declares AI use | `inconclusive` | `ingredient_ai_declaration` — each declaring ingredient identified with its manifest label, relationship, title, and its own validation/trust states |
> | 10 | Active not declared; no ingredient declares AI use | `no_signal` | `manifest_no_ai_declaration` — not evidence of human origin |
>
> Precedence notes: validation failures (5) and incomplete validation (6) take precedence over any declaration; an active-manifest declaration (7–8) takes precedence over ingredient declarations (9). Ingredient validation states are reported but never upgrade a result to `supports_ai`. Tests: one fixture or constructed library output per rule, plus an ordering test where conditions for two rules hold simultaneously.

**Implementation shape (proposed).**
- The rule engine is a pure function from a normalized record (format supported, error/timeout, store found, remote-only, active fields, ingredient declarations) to `(result, label)`.
- The library adapter produces that record. The engine never sees library objects, so every rule and every ordering can be tested with constructed records.

**How library outcomes reach the record:**
- Rule 3: `C2paError.ManifestNotFound` (VERIFIED: `Reader.try_create` returns `None` on exactly that exception).
- Rule 4: the remote-reference case (§e).
- Rule 2: any other `C2paError`, a `KeyError` from a store without a resolvable active manifest (`get_active_manifest`), a JSON error, or the timeout.

**Ordering tests (constructed records):** each case has the conditions of two rules true at once.
- 5 over 8: tampered integrity with an active AI declaration from an unknown signer.
- 5 over 7: invalid signature, trusted and declared.
- 6 over 7: `not_checked` integrity, trusted and declared.
- 7 over 9: active declared and trusted, and an ingredient also declares.
- 8 over 9: active declared and untrusted, and an ingredient also declares.
- 2 over 3: library error on an asset with no store.
- 1 over 2: unsupported format whose read would also fail. The adapter must not even call the library.

## e) Remote references (A1.2; A1.4.3; SPEC §7)

- A manifest available only by remote URL gives `inconclusive` / `remote_reference_only` (rule 4). It is **never fetched**.
- Library behavior on record (R0, `docs/decisions.md` R0.4):
  - With the A1.2 settings, `Reader` on the R0 remote-reference JPEG raised `C2paError` with a message beginning `must fetch remote manifests from url ...`.
  - That fixture was a JPEG with no embedded manifest whose XMP `dcterms:provenance` names the trap URL (`tests/test_offline_c2pa.py`, `_remote_reference_jpeg`).
- **Detection (proposed):**
  - Map `C2paError.RemoteManifest` (VERIFIED: subclass exists, `c2pa/c2pa.py`, `_C2paRemoteManifest`) to rule 4.
  - UNVERIFIED: whether the R0 error is that subclass or a generic `C2paError`. D1 records the exact exception class for both remote fixtures (the XMP one and a Builder `set_no_embed()` + `set_remote_url(trap_url)` one).
  - If it is generic, D1 proposes the detection rule for approval (for example, a message prefix match) and labels it fragile. Without an approved rule, the remote case falls to rule 2 (`error`). It is never treated as `no_credentials`.
- VERIFIED: `Reader.is_embedded()` and `Reader.get_remote_url()` exist. They need a constructed `Reader`, which fails when fetch is disabled, so they are recorded only when available.

## f) Offline configuration (Addendum A1.2), applied before every read

**API (VERIFIED, `c2pa/c2pa.py`):**
- `Settings()` (native `c2pa_settings_new`), then `Settings.set(path, value)`. The value is a JSON string; the method calls native `c2pa_settings_set_value` and raises `C2paError` if native rejects the path or value.
- `Context(settings=...)` attaches the settings. `Context.builder().with_settings(...)` (`ContextBuilder`) is an equivalent route.
- `Reader(format, stream, context=ctx)`.
- The deprecated module-level `load_settings` is not used. This is the same API the R0 tests use (`tests/test_offline_c2pa.py`, `_settings`, `_read`).

**Settings, set on a fresh `Settings` for every read (no shared or global state):**

| Path | Value (JSON) |
|---|---|
| `verify.remote_manifest_fetch` | `false` |
| `verify.ocsp_fetch` | `false` |
| `core.allowed_network_hosts` | `[]` |
| `core.decode_identity_assertions` | `false` |

Trust settings are in §h.

**R0 finding, restated:** the library **silently accepts unknown setting keys** (`test_c2pa_unknown_key_is_silently_accepted`; `docs/decisions.md`, R0.4, "Settings presence (A1.4.4): UNVERIFIED by acceptance"). Accepted settings are therefore **not evidence of effect**.
- Supporting R0 observation: each of the four keys rejects a wrong-type value with an error naming the key (`test_c2pa_offline_keys_are_type_checked`). An unknown key accepts any type.
- PRESENCE ONLY: the field names `remote_manifest_fetch`, `ocsp_fetch`, `allowed_network_hosts` and `decode_identity_assertions` occur in `c2pa_c.dll`, next to the `Verify` / `Core` settings structure names.
- Offline behavior is established only by §g.

**Tests (D1):**
- The analyzer's settings builder sets exactly these four paths, plus the §h trust paths.
- A failure in `Settings.set` disables the analyzer for that run (rule 2, `c2pa_error`, reason `c2pa_settings_rejected`).

## g) Offline evidence (Addendum B4; A1.4.1, A1.4.3)

All tests in this section start the loopback trap (`127.0.0.1:<random port>`, records every connection) and pass the analyzer's own settings builder.

- **Zero-connection test.** Run the remote-reference fixture, pointing at the trap, through the analyzer's code path with the production settings. Assert:
  - the trap records **0** connections;
  - the result is `inconclusive` / `remote_reference_only`.
- **Positive control (paired).** Same fixture, but with `verify.remote_manifest_fetch=true` and `core.allowed_network_hosts` = only the trap's `host:port`. Assert the trap **receives ≥ 1 connection**.
  - R0 already observed this for the XMP fixture: 1 connection, `GET /manifest.c2pa` (`test_c2pa_remote_reference_positive_control_reaches_trap`).
  - R1-D repeats it through the analyzer's settings builder, and for the Builder-made fixture.
- **Reporting:**
  - The result is reported as "zero attempted connections observed (with passing control)", for these fixtures and this configuration only.
  - It is reported separately from isolation claims: "passes under network isolation" (`docker --network none`) stays **not run**. Docker isolation is not run, and no image is pulled.
- **Failure handling:** if the control fails, or no remote-reference fixture can be built:
  - the trap result is invalid, and is reported as such;
  - the C2PA analyzer stays **disabled**: `--c2pa on` is refused with a message, and image segments keep the R0 placeholder.

## h) Trust configuration

- **Production trust list: packaged, versioned, empty.**
  - Proposed file: `src/litmus/provenance/trust/production_trust_anchors.json`, as package data. Content: `{"name": "production_trust_anchors", "version": 1, "anchors_pem": []}`.
  - It is loaded via `importlib.resources`, like the R1-C1 lexicons, and its SHA-256 is reported in every C2PA evidence record.
  - R1 code refuses a non-empty production list. Adopting anchors is OPEN, post-R1.
- **How it reaches the library.**
  - PRESENCE ONLY: the `Trust` settings structure names `user_anchors`, `trust_anchors`, `trust_config` and `allowed_list`, and the `Verify` structure names `verify_trust` and `verify_after_reading`, all in `c2pa_c.dll`.
  - Proposed paths: `trust.trust_anchors` (concatenated PEM, only when non-empty) and `verify.verify_trust = true` (A1.2: "trust verification stays on").
  - UNVERIFIED:
    - the exact paths;
    - whether an empty list should be expressed by not setting `trust.trust_anchors` or by setting it to an empty value;
    - whether the library carries any built-in C2PA trust anchors.

    Note: the DLL contains TLS root CA names, for example `Atos TrustedRoot Root CA ECC TLS 2021`. Their presence does not show they are used for C2PA trust.
  - Because unknown keys are silently accepted, D1 establishes the trust paths **by effect only**: the same test-CA-signed fixture must give `signingCredential.trusted` with the test anchor set, and must not give it under the production configuration.
- **Test anchors.**
  - They live only under `tests/fixtures/c2pa/` (test CA certificate, plus keys marked TEST ONLY) and are loaded only by tests, through the same settings builder with an explicit anchors argument.
  - Production code has no path or default pointing there.
- **Tests (D1/D2):**
  - The production list is empty: parse the packaged file and assert `anchors_pem == []`.
  - The production settings contain no test anchor: build the production settings dict and assert none of the test CA PEM, its SHA-256 or its subject appears.
  - No module under `src/` references `tests/fixtures/c2pa`: a source scan.
  - The trusted fixture under the production configuration maps to `signer_trust = unknown`.

## i) Explicit limitation (plan, README, and every report with C2PA evidence)

> With an empty production trust list, `signer_trust` is `unknown` for every manifest, so **no C2PA result can be `supports_ai` in R1**. A valid AI-use declaration alone yields `inconclusive` / `untrusted_signed_ai_declaration` (rule 8).

- This sentence is part of the C2PA evidence `limitations` on every record.
- It is part of the report-level limitations whenever C2PA runs.
- It is in the README.
- A test asserts its presence (R1-PLAN.md §1.4).

## j) Fixtures

- **Generator:** a committed script, `scripts/make_c2pa_fixtures.py`, writing to `tests/fixtures/c2pa/`.
  - It runs offline and uses only installed packages: `cryptography` (already present as a c2pa dependency; R1-PLAN.md §1.4), Pillow, and the library's `Builder`.
  - Signer construction (VERIFIED, `c2pa/c2pa.py`):
    - `C2paSignerInfo(alg, sign_cert, private_key, ta_url)` with `ta_url=None` (no timestamp authority, so no network);
    - `Signer.from_info`;
    - `Builder.sign(...)`.
  - `C2paSigningAlg` has ES256/384/512, PS256/384/512 and ED25519.
  - Proposed algorithm: ES256. Signatures and claim timestamps vary per run, so outputs are not byte-reproducible.
  - The script writes `tests/fixtures/c2pa/manifest.json` with each file's SHA-256, its generator parameters, and the library versions. Tests use the committed files; regenerating them is a reviewed change.
- **Test CA hierarchy:** generated locally (root → intermediate → end-entity). The end-entity certificate has the key usage and extended key usage C2PA expects for signing. The specific EKU OIDs are UNVERIFIED and will be recorded from the library's acceptance in D1.

**Fixture set (each one is JPEG unless noted; PNG and WebP get at least the no-manifest and trusted-signer variants):**

| Fixture | Built how | Expected rule |
|---|---|---|
| `trusted_signer` | signed by the test CA, test anchors loaded | 10 (tests); 10 with `signer_trust = unknown` under production |
| `untrusted_signer` | self-signed or other CA, not in the test anchors | 10, with `signer_trust = untrusted` (tests) |
| `no_manifest` | plain Pillow image | 3 |
| `tampered` | `trusted_signer` with image bytes changed after signing | 5 |
| `active_ai_declared` | active `c2pa.actions` with `trainedAlgorithmicMedia` | 7 with test anchors; 8 under production |
| `ingredient_ai_only` | active not declared; ingredient (`Builder.add_ingredient`) whose own manifest declares | 9 |
| `remote_reference` | `Builder.set_no_embed()` + `set_remote_url(trap_url)` (VERIFIED methods), plus the R0 XMP `dcterms:provenance` variant | 4 (and §g) |
| `not_checked_*` | **constructed** library output (JSON), labeled `constructed`, if no real fixture produces a `not_checked` state | 6 |

- **Risk (UNVERIFIED):** the library may reject self-generated certificates that lack required profile fields, such as extended key usage.
  - PRESENCE ONLY: `CertificateNotTrustedInvalidEku`, `EmptyEkuExtension` and `EndEntityUsedAsCaExtension` occur in `c2pa_c.dll`.
  - Fallback 1: the c2pa-python repository's test certificates, after a license check. The package license is MIT OR Apache-2.0; the certificates' own terms are UNVERIFIED. This needs Ryan's approval, because it adds third-party files.
  - Fallback 2: constructed library outputs for the affected rules, each labeled `constructed`.
- **Constructed outputs:** JSON shaped like real D1 output and committed under `tests/fixtures/c2pa/constructed/`. Each file states in its own content that it was constructed. Constructed outputs never count as evidence that the library emits that code.

## k) `unsigned_metadata` (EXIF/XMP outside manifests) — OPEN

SPEC §8.2: ordinary EXIF/XMP/IPTC outside any manifest goes in `unsigned_metadata`, is labeled unverifiable and editable, and never sets `result`.

- **RECOMMENDED: include a minimal, presence-level version in D3.** It uses Pillow, which is already installed and already used by ingestion.
  - EXIF via `Image.getexif()`: tag count, plus `Software`, `Make`, `Model`, `DateTime` if present, as strings truncated to 256 code points.
  - XMP: presence and byte length only, from Pillow's `info["xmp"]` where available. No XMP parsing.
  - The section is labeled "unverifiable; editable; not evidence", and a test asserts it never changes `result`.
- **Alternative:** defer to R2 and state "unsigned metadata not examined" in limitations.
- Either way it never sets `result`.

## l) Report integration

- **Placement:** C2PA `OriginEvidence` (SPEC §4.2) goes on **image segments only**, with `method_id = "c2pa_provenance"`, `raw_score = null` and `score_direction = null`.
  - `provenance` holds:
    - `manifest_present` (`embedded` / `remote_reference_only` / `none`);
    - the active manifest record and ingredient records (§b);
    - `mapping_version`;
    - the trust list name, version, SHA-256 and anchor count;
    - the library versions (`c2pa_python`, `sdk`);
    - the applied settings paths and values.
  - `details` holds `validation_state`, raw status codes per list, `unmapped_status_codes`, and timings.
  - `reasons` holds the rule label, plus `c2pa_timeout` / `c2pa_settings_rejected` where applicable.
  - `limitations` holds §i, "absence of Content Credentials is not evidence of human origin", "R1 checks provenance only; it does not detect AI-generated images", and the timeout limitation when relevant.
- **Activation (proposed):** `litmus analyze FILE --c2pa {off,on}`, **default `off`**.
  - Off: image segments keep the R0 placeholder, and the report is byte-identical to the golden files. This is tested the same way as `--quality off`.
  - On: the C2PA analyzer replaces the placeholder on image segments, with origin computed before quality. It is refused (exit 1, message) while D1's trap test or positive control is not passing at the current commit; that check is recorded as a constant flipped only with D1 evidence.
  - Whether the default becomes `on` is decided after D1–D3 (§n). It would change golden files and need approval.
- **Report-level limitations, when C2PA runs:** the §i sentence; "C2PA results describe provenance metadata, not image content"; "offline: remote manifests are not fetched".

## m) Checkpoints

### D1 — Fixture feasibility, settings, trap and control (analyzer still disabled)

- **Work:**
  - Fixture generator and test CA.
  - Committed fixtures and `manifest.json`.
  - The settings builder, offline and trust (§f, §h).
  - Recorded real library output (`json()`, validation state and results, exception classes) for every fixture, committed as golden library output.
  - Trap test and positive control through the settings builder, for both remote fixtures.
  - Trust-path effect test.
  - The production trust file and its emptiness tests.
- **Acceptance:**
  - Each fixture either builds, or is reported as not buildable with the library's error. Fallbacks are proposed, not applied.
  - The trap shows 0 connections with a passing control (≥ 1) for at least one remote fixture. Otherwise D1 reports failure and the analyzer stays disabled.
  - Trust paths are shown by effect, or reported UNVERIFIED with the analyzer staying disabled.
  - Exception classes for no-manifest, remote and tampered inputs are recorded.
  - Full default suite and Ruff pass; the tree is clean.
- **Tests:**
  - `test_c2pa_fixtures_match_manifest` (hashes);
  - `test_c2pa_settings_builder_sets_offline_paths`;
  - `test_c2pa_remote_reference_zero_connections_via_settings_builder[xmp|builder]`;
  - `test_c2pa_remote_reference_positive_control_via_settings_builder[xmp|builder]`;
  - `test_c2pa_trust_anchor_changes_signing_credential_code`;
  - `test_production_trust_list_is_empty`;
  - `test_production_settings_contain_no_test_anchor`;
  - `test_src_never_references_test_anchor_dir`;
  - `test_recorded_library_output_is_current` (re-reads fixtures and compares with the committed library output).

### D2 — Mapping and rule engine

- **Work:**
  - The status-code mapping table (§c) with `mapping_version`.
  - Normalization from library output to the record.
  - The pure rule engine (§d).
  - The timeout wrapper.
  - The declared-AI-use detector.
  - Ingredient extraction.
- **Acceptance:**
  - Every mapping row is demonstrated by real or constructed output; undemonstrated rows are listed.
  - All 10 rules are tested, plus the ordering tests.
  - Unmapped codes give rule 6.
  - The timeout gives rule 2.
  - Full default suite and Ruff pass.
- **Tests:**
  - `test_rule_{1..10}_*` (fixture where available, otherwise constructed and labeled);
  - `test_rule_order_*` (the §d list);
  - `test_mapping_row_*` (one per row);
  - `test_unmapped_code_gives_validation_incomplete`;
  - `test_positive_evidence_required_for_valid`;
  - `test_ingredient_states_never_upgrade_result`;
  - `test_declared_ai_use_exact_uris`;
  - `test_timeout_gives_error_and_limitation` (injected short timeout, stub read that blocks);
  - `test_settings_rejection_gives_error`;
  - `test_production_config_never_supports_ai` (every fixture under production config: result ≠ `supports_ai`).

### D3 — Report/CLI integration and docs

- **Work:**
  - `--c2pa {off,on}` and placement in `report.py`.
  - Limitations.
  - Optionally `unsigned_metadata` (§k).
  - `docs/interfaces.md` C2PA section: fields, mapping table, rules, settings, trust list, activation.
  - README limitation (§i).
  - A `docs/decisions.md` entry.
- **Acceptance:**
  - Default-off byte identity against the golden files, and `--c2pa off` equals the flag omitted.
  - With `on`: image segments carry C2PA evidence, text segments are unchanged, and the §i sentence is present.
  - The import-isolation test shows the C2PA path imports no torch/transformers/scorer modules.
  - Full default suite from inside and outside the repository; Ruff; pip check; non-ASCII audit.
- **Tests:**
  - `test_c2pa_default_off_byte_identical_to_golden`;
  - `test_c2pa_off_equals_omitted`;
  - `test_c2pa_on_image_segments[jpeg|png|webp]`;
  - `test_c2pa_on_text_segment_unchanged`;
  - `test_c2pa_limitation_sentence_in_every_record`;
  - `test_c2pa_refused_when_offline_evidence_missing`;
  - `test_c2pa_round_trip_to_json_from_json`;
  - `test_c2pa_import_isolation`;
  - if §k is included: `test_unsigned_metadata_never_sets_result`.

## n) Open decisions for Ryan

1. `unsigned_metadata` scope: minimal Pillow presence-level summary in D3 (RECOMMENDED), or defer to R2.
2. `--c2pa` default: `off` through D3 (RECOMMENDED); revisit after D3.
3. Fixture fallback if self-generated certificates are rejected: c2pa-python repository test certificates (after a license check), or constructed outputs only.
4. The eventual production trust list (post-R1). R1 ships an empty list.
5. Licensing remains **OPEN — pending Ryan's decision**.

## p) Approval and corrections (Ryan, 2026-10-30)

**Approval:** 2026-10-30: Ryan approved R1-D1 (feasibility) only; D2/D3 not approved.

**Correction 1 — context-aware mapping.**
- Validation codes are mapped by the manifest and assertion they belong to.
- An `assertion.action.ingredientMismatch` on the **active** claim affects the active manifest. It must not be discarded as an ingredient-only issue.
- D1 captures each status entry together with the manifest it was reported for (active vs ingredient, by label) and any assertion URL, so that D2 can map by context.

**Correction 2 — timestamps.**
- A timestamp failure need not invalidate the claim signature, and an `insideValidity` status does not by itself prove a verified signing time. The D2 mapping treats them separately:
  - `signature`: claim signature verification and credential status.
  - A separate timestamp state: whether a signing time was verified by a trusted timestamp. With no TSA in R1 fixtures, it is expected to be absent.
- **Specification source: UNVERIFIED.** No copy of the C2PA specification is available offline in this environment, and network access is not permitted. The specification section this relies on must be cited when D2 is planned; until then the claim is recorded as Ryan's instruction, not as a verified reading.

**Correction 3 — timeout is a response deadline, not cancellation.**
- **One dedicated worker per process** runs C2PA reads.
- **At most one outstanding C2PA task.** The analyzer waits up to the deadline (SPEC §6.2: 120 s) for its result.
- **On expiry** the segment gets `error` / `c2pa_timeout`. The task is not cancelled and keeps running on the worker.
- **While a timed-out task is still running**, new C2PA requests return `error` / `c2pa_worker_busy` immediately instead of queuing.
- **Ownership:** the task's input buffer, streams and library handles are owned by the worker and released when the task finishes, whether or not anyone is still waiting.
- **No accumulation of threads after timeouts:** the worker is never replaced while busy.

**Correction 4 — trust claims.**
- One untrusted fixture does not prove the SDK has no built-in anchors.
- SDK trust observations (status codes observed for specific fixtures and settings) are recorded separately from Litmus's policy.
- **Litmus's policy is an explicit, empty, packaged production anchor list.** No statement about built-in anchors is made beyond what was observed.

**D3 preferences (approved and implemented in D3):** a minimal unsigned-metadata summary (§k); `--c2pa` off by default (§l).

**Certificate fallback: pending.**
- If local certificate generation fails, report the exact failure and stop that branch.
- No third-party certificate or fixture files are added (this replaces the §j fallback 1 for now).

## o) Effort (ESTIMATE) and risks

**Effort (ESTIMATE, focused hours):**
- D1: 6–10 h. This has the most uncertainty: certificate profile, trust paths and remote fixtures.
- D2: 5–8 h.
- D3: 3–5 h.
- Total: **14–23 h**.

R1-PLAN.md §2 names R1-D among the most uncertain checkpoints.

**Risks:**
- **Certificate profile rejection** (§j). Mitigation: fallbacks 1–2, each needing approval.
- **Built-in trust anchors in the library** (§h, UNVERIFIED). Mitigation: the production-configuration test on a trusted fixture; the analyzer stays disabled if trust cannot be shown to be empty in effect.
- **Status-code emission differs from names present in the binary** (§c). Mitigation: strict positive-evidence rules; unmapped codes fall to `not_checked`.
- **Remote-reference error is not a typed exception** (§e). Mitigation: an approved detection rule, otherwise rule 2.
- **Uncancellable native call on timeout** (§a). Mitigation: daemon thread, reported limitation.
- **Sidecar fallback** when the library detects no container (`Reader.__init__` docstring). Mitigation: only ingested JPEG/PNG/WebP reach the analyzer, and the MIME type is passed explicitly.
- **Library version drift.** The pinned version (0.38.0 / SDK 0.91.0) is recorded in every record. An upgrade invalidates the D1 recorded output and the mapping until re-verified.
- **Windows-only native library in this environment** (`c2pa/libs/c2pa_c.dll`). Docker/Linux runs remain not run.

## q) D2 continuation (Ryan, 2026-10-30)

Ryan authorized completion of the interrupted D2 implementation, preserving
all existing work, using the existing `.venv`, and committing D2 plus evidence
before stopping for independent review. This supersedes earlier D2 approval
status lines; it does not authorize D3. HEAD at continuation was `e88a3e5`.

Implementation details and limits are in `docs/interfaces.md` (internal D2
interface). Actual checks are in `docs/decisions.md` and
`eval/results/r1d2_verification.json`. The production analyzer remains disabled.

- Remote-reference adapter: for pinned 0.38.0 / 0.91.0 only, the exact captured
  `Remote: must fetch remote manifests from url ` prefix is recognized when
  fetch is explicitly disabled. Builder and XMP variants have paired trap
  tests through the D2 pipeline. The adapter is fragile and version-gated.
- Empty production trust policy always returns `unknown`, independently of
  SDK trust observations. Trusted results are exercised only through an
  explicit policy defined under tests, with explicit test-anchor settings.
- Timestamp states are separate from claim signature. All timestamp cases
  are constructed policy tests; no real timestamp verification is claimed.
  The inherited partial generator named C2PA 2.5 section 14.8, but that
  section/text remains UNVERIFIED here. No specification copy was fetched.
- Unknown codes follow section c strictness rule 2, affecting both active
  integrity and signature unless already invalid. Positive evidence must
  occur in the success list. The mapping does not infer validity from the
  overall SDK validation state.
- Ingredient binding matches remain `not_checked` for the analyzed asset;
  attributed negative codes can make an ingredient `invalid`. Such states
  never upgrade the active result. Unreferenced manifests are diagnostic
  records, excluded from the ingredient declaration rule.
- The worker implements a response deadline, immediate busy response and
  recovery on the same thread, with worker-owned cleanup. Timeout never
  cancels native work. Tests use injected short deadlines and blocked stubs;
  a real native call hanging for 120 seconds was not induced.

## r) D3 approval and current evidence reconciliation (2026-10-30)

Ryan approved `R1-D3-BUILD-PROMPT.md` in the continuation instruction, including
offline installed-wheel verification using existing pinned runtime dependencies.
D2 closure is reviewer-reported: Codex independently reviewed `0c6fa08`, with
628 default tests, Ruff, pip check, both trap/control variants and bounded-worker
checks passing, and a clean tree. This is distinct from fresh D3 builder checks.

This section resolves the remaining earlier feasibility questions:

- Settings: every read uses fresh `Settings.from_dict` and `Context`. D1 trust
  effects and D2 remote effects were observed through that route; Settings.set
  acceptance is not proof of effect. Production requests all A1.2 offline keys
  plus verify_trust=true. Unknown setting keys remain silently accepted.
- Trust resource: `src/litmus/c2pa/trust/production_trust_anchors.pem`, packaged
  via setuptools and loaded by importlib.resources. It has six metadata headers
  and zero certificates, not the initially proposed JSON format. Litmus refuses
  nonempty production anchors and always maps production trust to unknown,
  independently of SDK diagnostics. No global SDK built-in-anchor claim follows.
- JSON: D1 real captures demonstrate active_manifest, manifests,
  validation_results.activeManifest, ingredientDeltas and ingredient links.
  Observed overall states include Valid, Trusted and Invalid. The mapper never
  uses overall state as proof of integrity/signature/trust.
- Mapping: D2 has 45 codes, with nine observed in real captures and 36 tested
  only through constructed injection. The authoritative table is in interfaces.
  Positive evidence must occur in success; invalid precedes not_checked.
  Unknown active codes make both fields incomplete unless invalid. Attribution
  uses manifest/assertion URLs; ingredient states never upgrade the active result.
- Remote adapter: generic C2paError with the exact captured prefix
  `Remote: must fetch remote manifests from url `, only at 0.38.0 / 0.91.0
  with fetch explicitly disabled. Both Builder and XMP variants have passing
  zero-connection/control pairs. No subtype-only assumption remains. These
  observations do not establish network isolation or behavior for every URL.
- Timestamp: the reviewer supplied C2PA 2.5 section 14.8, “Validate the time
  stamp,” at https://spec.c2pa.org/specifications/specifications/2.5/specs/C2PA_Specification.html#_validate_the_time_stamp.
  The builder did not independently fetch or verify that text. Timestamp
  failures remain separate from claim-signature failures. No real TSA was used;
  all project timestamp-validation cases remain explicitly constructed.
- Fixtures: local certificate generation succeeded. Actual scripts are
  `generate_c2pa_fixtures.py`, `capture_c2pa_outputs.py` and
  `make_c2pa_constructed.py`. No third-party certificate fallback was needed
  or adopted. Constructed fixture descriptions now attribute the citation to
  the reviewer; underlying stores and old captured/evidence records are preserved.
- Worker: the reviewed D2 worker already enforces one outstanding job, response
  deadline, immediate busy result, same-thread recovery and worker-owned cleanup.
  D3 adds reporting diagnostics only, without changing rule/worker semantics.
- D3: `--c2pa {off,on}`, default off, is implemented for accepted image segments.
  The old placeholder and golden bytes remain the default. Text-only/rejected
  inputs do not initialize the SDK. Minimal unsigned metadata is included only
  with enabled image C2PA and never changes origin results. See interfaces for
  exact fields, errors, limitations and wheel verification.

Remaining open work includes production anchors, licensing and later checkpoints.
Changing the default to on is not authorized. Real timestamp validation,
network isolation and Linux SDK execution remain undemonstrated.
