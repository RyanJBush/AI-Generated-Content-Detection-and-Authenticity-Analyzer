# SPEC v0.3 — Correction Addendum A (PLANNING DRAFT)

Applies to `SPEC.md` planning draft v0.3. Where this addendum and v0.3 differ, **this addendum governs**. Sections not mentioned are unchanged. Nothing here is approved for implementation; R1 and later remain unapproved. Markers as in v0.3 §0.

Sources checked 2026-10-26 by the spec author: c2pa-rs settings source (`sdk/src/settings/mod.rs`, `main` branch) and the PyPI index for c2pa-python (latest listed: 0.38.2). The `main` branch is **not** the pinned version; every setting below must be re-verified against the version actually pinned (A1.4).

---

## A1. Offline guarantee (replaces v0.3 §7)

### A1.1 Why v0.3 §7 was insufficient

A Python-level socket guard only intercepts Python's `socket` module. Native libraries (the c2pa-rs core behind c2pa-python, tokenizer/runtime native code) and subprocesses open connections without passing through it. Offline behavior must therefore be (1) disabled at each library's own configuration, and (2) tested by observing actual network attempts.

### A1.2 Configuration-level disables (each analyzer)

| Component | Required configuration |
|---|---|
| Text detector (R1) | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`; load by local path at pinned revision with `local_files_only=True`; missing files → `error` |
| C2PA (R1) | Settings applied before any read: `verify.remote_manifest_fetch = false`; `verify.ocsp_fetch = false`; `core.allowed_network_hosts = []` (an empty list blocks all SDK HTTP traffic, per the c2pa-rs source). Also `core.decode_identity_assertions = false`, because the c2pa-rs source carries a warning that the CAWG identity assertion does not currently respect the network setting (warning attribution UNVERIFIED; disabling it is the conservative choice). Trust list loaded from a local file; trust verification stays on. |
| Quality observers, ingestion, image decode | No network-capable code paths; no subprocesses |
| Subprocesses | None permitted in analysis code (enforced by a test that patches `subprocess` to raise during analysis) |

### A1.3 Process-level guard (defense in depth, not the guarantee)

A Python socket guard that **allows loopback only** (`127.0.0.1`, `::1`) and raises on any other destination. Loopback is required for the local UI server and its test client. The UI binds to `127.0.0.1` only.

### A1.4 Behavior tests (required; R0 for the harness, R1 per analyzer)

1. **Loopback trap server:** a test starts an HTTP listener on `127.0.0.1:<random port>` that records every connection.
2. **HF offline test (R1):** set `HF_ENDPOINT` to the trap URL, load the text detector from local files, assert the trap received **zero** connections.
3. **C2PA remote-fetch test (R1; harness built in R0):** analyze a fixture whose manifest is a remote reference pointing at the trap URL, with the settings in A1.2; assert zero connections and result `inconclusive` / `remote_reference_only`. If such a fixture cannot be produced, this test is **not run** and the C2PA analyzer stays **disabled** until it passes.
4. **Settings presence test:** with the pinned c2pa-python, apply each A1.2 setting and assert the library accepts it (an unknown key must fail the test, not be ignored silently). If a key does not exist in the pinned version, the analyzer stays disabled and the spec is revised.
5. **OS-level isolation (CI):** run the model-free test suite in a Linux container started with networking disabled (e.g., `docker run --network none`). Tests must pass, proving no test depends on network access. This covers native code and subprocesses for whatever runs in that suite.
6. **Loopback UI test:** start the UI on `127.0.0.1`, issue one request from the test client, assert success; assert the server is not reachable on a non-loopback interface address.

## A2. C2PA result rules (replaces the v0.3 §8.2 result table)

Rules are evaluated **in order; the first matching rule determines `result`**. This makes outcomes mutually exclusive.

| # | Condition (active manifest unless stated) | `result` | Label |
|---|---|---|---|
| 1 | Format not supported by the pinned c2pa library | `not_supported` | `c2pa_format_unsupported` |
| 2 | Library error or timeout | `error` | `c2pa_error` |
| 3 | No manifest store found | `inconclusive` | `no_credentials` |
| 4 | Only a remote manifest reference (not fetched, A1) | `inconclusive` | `remote_reference_only` |
| 5 | `integrity = invalid` **or** `signature = invalid` | `inconclusive` | `validation_failed` — declarations shown, not used as evidence |
| 6 | `integrity = not_checked` **or** `signature = not_checked` | `inconclusive` | `validation_incomplete` |
| 7 | `declared_ai_use = declared` and `signer_trust = trusted` | `supports_ai` | `trusted_provenance_ai_declared` |
| 8 | `declared_ai_use = declared` and `signer_trust ∈ {untrusted, unknown}` | `inconclusive` | `untrusted_signed_ai_declaration` |
| 9 | Active not declared; ≥1 ingredient manifest declares AI use | `inconclusive` | `ingredient_ai_declaration` — each declaring ingredient identified with its manifest label, relationship, title, and its own validation/trust states |
| 10 | Active not declared; no ingredient declares AI use | `no_signal` | `manifest_no_ai_declaration` — not evidence of human origin |

Precedence notes: validation failures (5) and incomplete validation (6) take precedence over any declaration; an active-manifest declaration (7–8) takes precedence over ingredient declarations (9). Ingredient validation states are reported but never upgrade a result to `supports_ai`. Tests: one fixture or constructed library output per rule, plus an ordering test where conditions for two rules hold simultaneously.

## A3. Pre-evaluation data preparation for R1 text (adds to v0.3 §10; must be final before any R1 evaluation code)

1. **Metadata-only selection.** Candidate groups are chosen using RAID metadata fields only (`id`, `source_id`, `adv_source_id`, `model`, `decoding`, `repetition_penalty`, `attack`, `domain`). Generation text is not read during selection.
2. **Seed and split.** One recorded integer seed. Split key = SHA-256(`seed` ‖ `source_id`); first 30% of key space → dev, remainder → test.
3. **Quotas.** English domains only; per-domain quota = equal share of the target group count (domains with too few groups contribute all they have; shortfall recorded). Within each domain, one clean machine row per group selected by seeded hash, giving roughly equal coverage of generators; per-generator counts recorded. Attacks: paraphrase, homoglyph, zero_width_space only.
4. **Eligibility (text is read only now, only for selected candidates):** valid per v0.3 §6.1 text rules; ≥ 64 retained tokens.
5. **Duplicate checks across groups:** (a) raw-text SHA-256 of the exact decoded string; (b) retained-token hash = SHA-256 of the scored token-ID sequence (first ≤ 512 IDs). Any collision across different groups removes all colliding rows from both groups. Within-group attacked rows identical to their clean parent are kept and counted as no-op attacks.
6. **Pair and attack cleanup (single ordered pass):** remove colliding rows → drop groups lacking either a clean human or a clean machine row → drop attacked rows whose clean parent was removed → assert invariants (each kept group has exactly one clean human and one clean machine row; every attacked row has its clean parent in the same group and split). Removals cannot create new collisions, so no iteration is needed.
7. **Manifest:** all selected IDs, exclusions with reasons, counts per split/domain/generator/attack, seed, dataset revision, and file hashes, written before any scoring.

## A4. Binoculars math and calibration hash (final before the R1 scorer is implemented)

**Inputs.** `ids` = observer tokenizer applied to the decoded text with `add_special_tokens=False`, `split_special_tokens` = value fixed by the R1 tokenizer check, right truncation to 512 tokens. `T = len(ids)`; if `T < 64` → `inconclusive`, `too_short`. Batch size 1, so there is no padding (if batching is added later, all sums use the attention mask).

**Per position** `t` (0-based), with logits from one forward pass of each model on `ids`:
`O[t] = log_softmax(observer_logits[t])`, `P[t] = log_softmax(performer_logits[t])`, both computed in float32 over the full vocabulary.

**Numerator (performer NLL, shifted):** `NLL_perf = (1/(T−1)) · Σ_{t=0}^{T−2} −P[t][ids[t+1]]`
**Denominator (cross-entropy over all positions, including the final one):** `XENT = (1/T) · Σ_{t=0}^{T−1} Σ_v exp(O[t][v]) · (−P[t][v])`
**Score:** `B = NLL_perf / XENT`. Validation: all finite, `NLL_perf ≥ 0`, `XENT > 0`; otherwise `error` with the failing quantity named. `score_direction = lower_means_more_machine`; machine-positive score `r = −B`.

This follows the upstream reference positional convention (§17 [1], pinned commit c8ae2f9) with two documented deviations: float32 reductions and attention-mask (not pad-ID) masking.

**`scoring_config_hash`** = SHA-256 of canonical JSON (UTF-8, sorted keys, no insignificant whitespace) containing exactly:
`scorer_version`; `formula_id = "binoculars_shiftednll_allposxent_v1"`; `observer_repo` + `observer_commit`; `performer_repo` + `performer_commit`; `tokenizer_json_sha256`; `add_special_tokens`; `split_special_tokens`; `truncation_side = "right"`; `max_tokens = 512`; `min_tokens = 64`; `weight_dtype`; `reduction_dtype = "float32"`; `score_direction`.
**Not** in the hash (recorded in the report's environment block): device, driver version, torch/transformers versions, CPU/GPU model. A changed environment requires a numerical smoke check before reusing a calibration for published results.

## A5. Extraction coverage vs. scored window (adds to v0.3 §4.2 and §6.4)

- **Extraction coverage** (report-level and per segment `extraction`): how much of the input became segments. For an R1 text file: decoded code points in segment / decoded code points in file (100% when accepted).
- **Scored window** (per OriginEvidence, new field `details.scored_window`): `{tokens_total, tokens_scored, truncated: bool, scored_char_range: [0, end)}` in the segment's local text frame. A truncated detector window never lowers extraction coverage, and full coverage never implies the whole text was scored.

## A6. Empty input and boundary cases (adds to v0.3 §6)

| Case | Behavior |
|---|---|
| 0-byte file (any extension) | `not_supported`, `empty_input` |
| File empty after BOM removal/decoding | `not_supported`, `empty_after_decoding` |
| Whitespace-only text | Accepted. Detector: `inconclusive`, `too_short`. Quality: `none_found`; `rate_per_100_words = null` when word count is 0 |
| Control-character check | Computed only on non-empty decoded text; threshold is strict: reject when share ≥ 1% |
| File size exactly 50 MB | Accepted (limit is ≤) |
| Decoded text exactly 200,000 code points | Accepted |
| Exactly 64 tokens | Scored; 63 → `too_short` |
| Exactly 512 tokens | Scored, `truncated = false`; 513 → `truncated = true` |
| Image exactly 50 megapixels | Accepted; above → `not_supported` |
| Analyzer runtime exactly at timeout | Treated as timeout (`error`) |

## A7. README corrections

README section references updated to v0.3 numbering: open decisions → `SPEC.md` §15; third-party terms → `SPEC.md` §17; plus a pointer to this addendum.

## A8. Effort note

The added R0 test work (A1.4, A6) may move R0 toward the top of its 8–14 h estimate. The roadmap total stays an ESTIMATE of 128–214 h until R0 is measured.
