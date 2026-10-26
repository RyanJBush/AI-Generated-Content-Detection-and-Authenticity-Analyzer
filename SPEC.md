# SPEC.md — Litmus (multimodal) — PLANNING DRAFT v0.3

Status: **PLANNING DRAFT — not approved for implementation.** **Correction Addendum A (`SPEC-v0.3-ADDENDUM-A.md`) governs where it differs from this file.** Supersedes the retired text-only SPEC, preserved at recovery tag `litmus-text-before-multimodal-2026-10-26`.
Owner / final decision-maker: Ryan. Planner/reviewer: ChatGPT/Codex. Implementer: Claude Code, only after approval. Prior file-ownership and interface agreements are retired (§14).

**Scope of detail:** R0 and R1 are specified to be implementable without further specification rounds (§4–§11). R2–R4 sections are **PROVISIONAL outlines** and will be specified in their own drafts before work starts.

Markers: **VERIFIED** (checked against a primary source in §17) · **REVIEWER-VERIFIED** (checked by Codex, not the spec author) · **UNVERIFIED** (must be checked before relying on it) · **PROPOSED** (awaiting approval) · **PROVISIONAL** (stands only if §9 gates pass) · **BLOCKED** (may not be used until a stated condition is met) · **OPEN** (decision for Ryan, §15) · **ESTIMATE** (forecast, not a measurement).

---

## 1. Goal

Examine text, images, audio, video, and documents for evidence of AI generation or manipulation, and report that evidence per segment, with its method, evaluation basis, and limitations.

## 2. Principles (binding for every release)

1. Origin evidence and quality observations are different record types (§4) and are never combined.
2. `inconclusive` is a first-class origin result, always with a reason.
3. No uncalibrated probabilities. Raw scores are labeled as scores; flags require a valid calibration (§10.4).
4. Claims are limited to evaluated tasks.
5. Per-segment reporting; no document-level "AI percentage."
6. Absence is not evidence: no manifest, no metadata, or a low score does not establish human origin.
7. Analysis is offline (§7). Analyzed content never leaves the machine.
8. Honest records: only executed, verified actions and results are recorded, attributed to whoever verified them.

## 3. Non-goals

Cross-modal fusion or document-level verdicts; attribution to a specific model or person; key-dependent watermark detection; OCR, speech-to-text, translation; real-time analysis; training large models; network transmission of analyzed content; use as the sole basis for punitive decisions.

## 4. Record schema (R0)

### 4.1 Segment

```
Segment
  segment_id        # "s0" for root, then "s1", "s2", ... in creation order
  parent_id         # null for root
  modality          # container | text | image | audio | video
  derivation        # transform chain from parent bytes (§5.2)
  coords_in_parent  # location in the PARENT's local frame (§5.3); null for root
  local_frame       # this segment's own coordinate system, used by its children and its spans (§5.3)
  content_sha256    # SHA-256 of the exact bytes analyzed (text: UTF-8 encoding of the decoded string)
  extraction        # {status: complete | partial | failed | skipped, notes[]}
  origin[]          # OriginEvidence
  quality[]         # QualityObservation (text only in R1)
```

### 4.2 OriginEvidence

```
OriginEvidence
  method_id, method_version
  result            # supports_ai | no_signal | inconclusive | not_supported | error
  raw_score         # number or null; never called a probability
  score_direction   # "higher_means_more_machine" | "lower_means_more_machine" | null
  calibration       # null or {scoring_config_hash, dev_set_id, alpha, threshold_c, n_dev_negatives, created}
  provenance        # C2PA only (§8.2); null otherwise
  reasons[]         # required unless result is supports_ai or no_signal
  limitations[]     # always present
```

- Scored detector: `supports_ai` only if a valid calibration exists for its exact configuration and the score satisfies §10.4. Calibrated but not past threshold: `no_signal`. No calibration: `inconclusive`, reason `"no calibration for this configuration"`, `raw_score` reported.
- C2PA result rules: §8.2.

### 4.3 QualityObservation

```
QualityObservation
  observer_id, observer_version
  status            # observed | none_found | not_supported | error
  count, rate_per_100_words
  spans[]           # [start, end) in the segment's local text frame
  notes[]
```

No `result`, score, or threshold. Never affects OriginEvidence.

## 5. Segment ancestry and coordinates (R0)

### 5.1 Ancestry

Root = the input file. Children come only from extraction. Each non-root segment has exactly one parent; the tree is acyclic. R1 shapes: text file → one root text segment; image file → one root image segment. (R2+: PDF file → page → text block | embedded image; DOCX file → text block | embedded image; video → track → frame/audio. PROVISIONAL.)

### 5.2 Derivation

Ordered list of transform names from parent bytes to analyzed content, e.g. `["utf8_decode"]`, `["image_decode"]`. R2+ examples: `pdf_text_layer`, `docx_paragraphs`, `embedded_image_raw`, `audio_decode`, `resample_16k_mono`.

### 5.3 Parent versus local coordinates

Every segment has two coordinate notions:

- **`coords_in_parent`** — where the segment sits, expressed in the parent's `local_frame`.
- **`local_frame`** — the segment's own system. Spans in its QualityObservations and the `coords_in_parent` of its children use this frame.

Root coordinates are not derived through the tree; a consumer composes them by walking ancestry. All ranges are half-open; all indices 0-based.

| Segment | `local_frame` | `coords_in_parent` |
|---|---|---|
| Text (R1 root) | `text_codepoints`: Unicode code-point offsets into the decoded string (no normalization) | null (root) |
| Image (R1 root) | `pixels`: `[x, y]` in the decoded image, origin top-left, full resolution | null (root) |
| PDF page (R2, PROVISIONAL) | `pdf_points`: PDF user space, origin bottom-left | `{page_index}` |
| PDF text block (R2) | `text_codepoints` of the block's extracted text | `{bbox: [x0,y0,x1,y1]}` in `pdf_points` |
| DOCX text block (R2) | `text_codepoints` | `{paragraphs: [p_start, p_end)}` in body order |
| Embedded image (R2) | `pixels` | PDF: `{bbox}` in `pdf_points`; DOCX: `{part_name}` |
| Audio track (R3) | `seconds` + `sample_rate` | `{track_index}` |
| Video frame (R4) | `pixels` | `{t_seconds, frame_index}` |

## 6. Ingestion (R0/R1)

### 6.1 Type detection

1. **Binary signatures first:** JPEG (`FF D8 FF`), PNG (`89 50 4E 47 0D 0A 1A 0A`), WebP (`RIFF....WEBP`). ZIP (`50 4B 03 04`) is treated as a container candidate (§6.3), never as text.
2. **Signatureless text:** plain text has no magic bytes. A file with no recognized binary signature is accepted as text only if all hold:
   - extension is `.txt` or `.md` (case-insensitive);
   - it decodes strictly as UTF-8 (optional UTF-8 BOM removed), or as UTF-16 LE/BE when a matching BOM is present;
   - the decoded string contains no NUL characters, and control characters other than `\t \n \r \f` make up less than 1% of characters.
   Otherwise `not_supported` with the specific failing check as the reason.
3. Extension/content mismatches (e.g. `.jpg` with PNG bytes): analyze by content, add a note.

### 6.2 R1 formats and limits

| Item | R1 rule |
|---|---|
| Formats | Text: `.txt`, `.md`. Images: JPEG, PNG, WebP. C2PA support per format: UNVERIFIED; checked in R0 against the c2pa library's supported-format list; unsupported formats get C2PA `not_supported` |
| Max file size | 50 MB |
| Max decoded text | 200,000 code points (else `not_supported`) |
| Text detector window | first 512 tokens scored; minimum 64 tokens (else `inconclusive`, reason `too_short`); truncation reported |
| Max image | 50 megapixels (decompression-bomb guard; decode refused above) |
| Per-analyzer timeout | 120 s per segment → `error` with reason |

Nothing is silently truncated.

### 6.3 ZIP-based DOCX (R2, specified now so R0 rejects correctly)

- R0/R1: any ZIP is `not_supported` (`"documents arrive in R2"`).
- R2 (PROVISIONAL): a ZIP is DOCX only if `[Content_Types].xml` exists and declares the main document part content type `application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml`. Macro-enabled main parts (`application/vnd.ms-word.document.macroEnabled.main+xml`) or a `vbaProject.bin` part → `not_supported`. Any other ZIP → `not_supported` (no general archive support). Zip-bomb guards: ≤ 2,000 entries, ≤ 200 MB total uncompressed, ≤ 100:1 per-entry compression ratio; no path traversal; nothing is written to disk outside a temp directory.

### 6.4 Extraction coverage

Every report includes coverage: segments created, items skipped with reasons. R1: always complete for accepted inputs (single segment). R2+ must report gaps (no text layer, text in images, form fields, comments, tracked changes).

## 7. Offline enforcement (every analyzer)

| Component | Enforcement |
|---|---|
| Process-wide (CLI, UI, tests) | Before any analyzer runs, set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, and install a guard that makes outbound socket connections raise. Local UI binds to `127.0.0.1` only. |
| Text origin detector | Load models from a local directory at pinned revisions with `local_files_only=True`; missing files → `error` ("model not installed; run setup"), never download |
| Text quality observers | Pure Python; no I/O beyond the input |
| C2PA provenance | Read only the embedded manifest store. Remote manifests (referenced by URL) are **not fetched**: report `manifest_present: remote_reference_only`, result `inconclusive`. Whether c2pa-python can disable remote fetching through its settings is UNVERIFIED (check in R0); regardless, the socket guard blocks it, and an attempted fetch is reported as `error`. Trust list read from a local, versioned file. No OCSP/CRL checks. |
| Image decoding | Local library decode only |
| Setup commands | The only network-enabled entry points; separate commands; record what was downloaded with hashes |
| Tests | Model-free test suite runs with the socket guard active; a test asserts that an outbound connection attempt fails |

## 8. R1 methods

### 8.1 Text origin — PROVISIONAL

Binoculars-style likelihood ratio (§17 [1]): observer = base model, performer = instruct model sharing one tokenizer; score `B = NLL_performer / XENT(observer‖performer)`, lower B = more machine-like, so `score_direction = lower_means_more_machine`. Candidate pair: a small base/instruct pair from one family (candidate Qwen2.5-0.5B / -Instruct); license gate UNVERIFIED (§9). Reuse of the retired scorer's tested math is OPEN (O2).

### 8.2 Image provenance (C2PA) — PROPOSED

**Which manifest.** The **active manifest** (the one describing the current asset) is evaluated separately from **ingredient manifests** (manifests of assets used to make it). Every declaration is reported with: `manifest_label`, `is_active` (bool), and for ingredients `relationship` (e.g. parentOf / componentOf, as reported by the library) and ingredient title.

**Per manifest fields** (none implies another):

| Field | Values |
|---|---|
| `integrity` | valid / invalid / not_checked — content bindings match the bytes (active manifest only; ingredients' bindings refer to other assets) |
| `signature` | valid / invalid / not_checked — claim signature verifies; certificate valid at signing time |
| `signer_trust` | trusted / untrusted / unknown — chains to an entry in the local trust list; `unknown` if no trust list configured |
| `declared_ai_use` | declared / not_declared — an actions assertion uses IPTC digital source type `trainedAlgorithmicMedia` or `compositeWithTrainedAlgorithmicMedia` (§17 [9]) |

**Result rules (applied to the active manifest; ingredients are reported, not decisive):**

| Condition | `result` | Reason / label |
|---|---|---|
| No manifest store | `inconclusive` | "no Content Credentials; no image detector in R1" |
| Remote reference only | `inconclusive` | "remote manifest not fetched (offline)" |
| Integrity or signature invalid | `inconclusive` | "manifest failed validation"; declaration shown but **not** treated as evidence |
| Valid + trusted + declared | `supports_ai` | **trusted provenance**: AI use declared by a trusted signer |
| Valid + untrusted/unknown + declared | `inconclusive` | **untrusted signed declaration**: shown as "AI use declared by an unverified signer" |
| Valid + not declared (any trust) | `no_signal` | "manifest present; no AI-use declaration" — not evidence of human origin |
| Active not declared, ingredient declared | `inconclusive` | "an ingredient declares AI use"; ingredient identified |

Ordinary EXIF/XMP/IPTC outside any manifest goes in `unsigned_metadata`, labeled unverifiable and editable, and never sets `result`.

**R1 provides image provenance, not image detection.**

### 8.3 Text quality — PROPOSED

Observers: stock phrases, hedges, repeated word 3-grams, claim phrases to inspect. Lexicons are versioned files. Tests: unit, metamorphic, span integrity. No accuracy claim.

## 9. Adoption gates (any model, checkpoint, or dataset)

1. **License** read from the primary source(s) and recorded with date. If sources conflict, the artifact is **BLOCKED** until the conflict is resolved by the licensor or by a written decision from Ryan after reading both texts. No conflict is resolved by assumption.
2. **Access:** official download route works; checksums recorded.
3. **Feasibility:** load and inference measured on the local GPU (re-verified in R0).
4. **Overlap:** checkpoint training data documented and checked against evaluation data (§10.6).

## 10. Evaluation methodology

### 10.1 Data roles

Train (trainable components only) · Dev (thresholds and diagnostics only) · Test (scored once per frozen configuration; never informs choices).

### 10.2 Grouping

A **group** is the unit of splitting and resampling. Every row belongs to exactly one group, and all rows of a group go to the same split.

- **Text (RAID):** group = one `source_id`: its human text, its machine continuations, and all attacked variants (via `adv_source_id`). R1 clean core: one human + one machine row per group, plus attacked variants of those rows.
- **Images (R2, PROVISIONAL):** group = **duplicate identity**: images connected by exact SHA-256 match of decoded pixels or by near-duplicate match (perceptual hash within a fixed Hamming distance, value set in R2 and frozen before test). Connected components form groups. This replaces v0.2's category grouping.
- **Audio/video (R3–R4, PROVISIONAL):** speaker (audio); source video with all its manipulations (video).

### 10.3 Text sample (R1)

Target ~1,000 groups from RAID train (official test labels are hidden, so RAID test is not used): dev ≈ 300 groups, test ≈ 700 groups, assigned by seeded hash of `source_id`. Final N set by the R0 runtime benchmark (ESTIMATE until measured). Attacks: paraphrase, homoglyph, zero_width_space, paired with their clean originals.

### 10.4 Thresholds — exact rule

1. Each detector declares `score_direction`. Define the **machine-positive score** `r = raw_score` if higher-means-more-machine, else `r = −raw_score`.
2. Negatives = dev rows labeled human (clean rows only). `N` = number of negatives.
3. Candidate thresholds = the set of distinct observed `r` values among dev negatives.
4. Decision rule: **flag iff `r > c`** (strict). Ties at `c` are not flagged.
5. Choose the **smallest** candidate `c` with `#{negatives with r > c} / N ≤ α`. The maximum observed negative score always qualifies (0 false positives), so a threshold always exists when `N ≥ 1`.
6. Minimum `N`: 200 for α = 5%; 1,000 for α = 1%. Below the minimum, no calibration is created for that α.
7. **Consequence for R1 text:** dev ≈ 300 groups gives ≈ 300 negatives, so **the 1% calibration is disabled for text in R1**; only the 5% calibration may be created, and it requires ≥ 200 negatives after all exclusions.
8. The calibration file records `scoring_config_hash`, `alpha`, `threshold_c`, `score_direction`, `N`, and the dev manifest hash. Any change to models, revisions, tokenizer settings, preprocessing, or scorer version changes the hash and invalidates it.

### 10.5 Metrics

Primary: clean-set AUROC (ties count 0.5); TPR and actual test FPR at the frozen 5% threshold. Attacks: paired comparison (detection rate on attacked vs. clean originals at the same threshold). Exploratory: per-slice results, descriptive only.

### 10.6 Overlap checks

- Text LM pair: pretraining data not fully documented; RAID human sources (e.g., Wikipedia, news) may appear in pretraining; reported as an unquantified contamination risk.
- Exact-duplicate check (SHA-256 of text) across groups; cross-group duplicates removed from both sides before splitting; counts reported.
- R2+: checkpoint training sources identified (UNVERIFIED for UnivFD and AASIST); in-distribution results labeled as such.

### 10.7 Bootstrap — paired-group procedure

1. Resample **groups jointly** (not per class): draw `G` groups with replacement from the `G` test groups.
2. A drawn group contributes **all of its rows**; a group drawn `k` times contributes its rows `k` times (multiplicity retained). Paired clean/attack rows therefore stay together.
3. Compute each statistic on the replicate using the frozen threshold.
4. 1,000 replicates, fixed seed recorded; percentile 95% interval.
5. **Undefined replicates:** a replicate in which a statistic is undefined (e.g., no negatives → FPR undefined; one class absent → AUROC undefined) is excluded **for that statistic only** and counted. Report the count. If more than 5% of replicates are undefined for a statistic, report "interval not reported (unstable resampling)" with the point estimate.
6. Intervals are conditional on the frozen threshold; calibration uncertainty is a stated limitation.

### 10.8 Insufficient data

A slice with < 30 groups or < 50 rows in either class: counts and point estimate only, labeled "insufficient data; no interval." A slice missing a class: AUROC "undefined." Anything not computed: "not run" with reason.

### 10.9 Freeze

Before test scoring, write a freeze record (config hash, thresholds, data manifest hash, lexicon hashes). Test scoring refuses to run on mismatch. Each test access is appended to a run log.

## 11. R0/R1 work breakdown and acceptance (implementable now, once approved)

| Item | Done when |
|---|---|
| R0.1 Schemas §4 as dataclasses + JSON (de)serialization | Round-trip tests pass; invalid enum values rejected |
| R0.2 Ingestion §6.1–6.2 | Tests: each signature; signatureless text accept/reject cases (bad UTF-8, NUL, >1% control chars, wrong extension); ZIP → not_supported; size/pixel limits |
| R0.3 Ancestry/coordinates §5 | Tests: tree validity; root-only shapes for R1 |
| R0.4 Offline guard §7 | Test: outbound connection raises; analyzers run with guard active |
| R0.5 CLI `litmus analyze FILE` → report JSON | Golden-file tests on fixtures |
| R0.6 Hardware/feasibility re-check | Recorded GPU/driver/torch; load test of the provisional text pair (after its license gate) |
| R1.1 Text detector (§8.1) | Hand-computed math tests; too_short and truncation paths; no-calibration → inconclusive |
| R1.2 Text quality observers (§8.3) | Unit, metamorphic, span-integrity tests |
| R1.3 C2PA provenance (§8.2) | Fixture tests for every row of the result table (fixtures: OPEN, O10) |
| R1.4 Evaluation (§10) on RAID | Grouped splits, 5% calibration, freeze, paired bootstrap; results with counts and intervals |
| R1.5 Local UI (127.0.0.1 only) | Smoke test without models; shows reasons, limitations, and "not a probability" note |

## 12. Releases and effort (ESTIMATE, focused hours)

| Release | Contents | Effort |
|---|---|---|
| R0 | §11 R0 items | 8–14 |
| R1 | Text origin + text quality + **image provenance** + local UI | 25–40 |
| R2 (PROVISIONAL) | Image detector (UnivFD-style) on GenImage; PDF/DOCX segmentation | 30–50 |
| R3 (PROVISIONAL) | Audio detector (AASIST-style) on ASVspoof 2019 LA; out-of-domain set BLOCKED (§13) | 25–40 |
| R4 (PROVISIONAL) | FF++ face-manipulation detection only; audio track via R3 | 40–70 |
| **Total** | | **128–214** |

**The roadmap totals an estimated 128–214 focused hours. R1 provides image provenance, not image detection.** Estimates exclude download, approval waits, and review time.

## 13. Future-phase data notes (PROVISIONAL)

| Dataset | Status | Notes |
|---|---|---|
| GenImage (R2) | License VERIFIED: CC BY-NC-SA 4.0 plus Dataset Terms that prevail on conflict; non-commercial only (project page). | Official download routes: Google Drive folder announced in the official repository README (news dated 2024-03-15) and Baidu Netdisk. Unofficial mirrors not used unless checksums match an official copy. Held-out-generator protocol: R2 spec will fix the training generator(s); held-out generators are excluded from probe training, dev threshold selection, and every model/hyperparameter choice, and reported only on test. |
| ASVspoof 2019 LA (R3) | VERIFIED: ODC Attribution; academic and commercial use. | Official train/dev/eval preserved. |
| In-the-Wild (R3) | **BLOCKED.** Conflicting license statements: project page says Apache-2.0; Hugging Face card says CC BY-SA 4.0. | Not adopted until the licensing that applies to the specific artifact downloaded is established (§9.1). No assumption. |
| FaceForensics++ (R4) | VERIFIED: non-commercial research/education only; access by request. | Requires O5. |

## 14. Collaboration

Single-writer by default: Claude Code implements approved work; ChatGPT/Codex plans and reviews. Concurrent coding requires a Ryan-approved `docs/interfaces.md` (ownership, shared schemas, analyzer interface, config hash, calibration format, GPU scheduling, merge procedure). **OPEN.**

## 15. Open decisions for Ryan

| # | Decision |
|---|---|
| O1 | Approve R0/R1 scope and §11 work breakdown |
| O2 | Reuse retired text-scorer design/tests from the recovery tag (explicit approval required) |
| O3 | Paid compute/API/storage budget |
| O4 | Deployment target (R1 is local-only, 127.0.0.1) |
| O5 | Commercial vs non-commercial use (GenImage, FF++ are non-commercial only) |
| O6 | Project license |
| O7 | Text model pair (after license gate) |
| O8 | In-the-Wild: obtain licensing clarification, or drop/replace the out-of-domain audio set |
| O9 | GenImage route: Google Drive vs Baidu (both official); record checksums |
| O10 | C2PA fixture source and trust list |

## 16. Verification log

| Item | Result | Verified by |
|---|---|---|
| Project folder contains only `.git` | Confirmed | REVIEWER-VERIFIED (Codex), 2026-10-26 |
| Recovery tag resolves to `106a645` | Confirmed | REVIEWER-VERIFIED (Codex), 2026-10-26 |
| Spec author's own repository checks | Not run (no repository access) | — |
| GenImage Google Drive route | Present in official repository README | Spec author, 2026-10-26 |
| Dependencies, models, datasets | Not installed or downloaded | — |

## 17. References (checked 2026-10-26)

1. Hans et al., Binoculars, ICML 2024, arXiv:2401.12070; code github.com/ahans30/Binoculars (BSD-3-Clause at commit c8ae2f9).
2. Dugan et al., RAID, ACL 2024, arXiv:2405.07940; dataset card huggingface.co/datasets/liamdugan/raid (license: mit; test labels hidden).
3. Ojha, Li, Lee, CVPR 2023, arXiv:2302.10174; github.com/Yuheng-Li/UniversalFakeDetect (MIT).
4. Zhu et al., GenImage, NeurIPS 2023 D&B, arXiv:2306.08571; project page genimage-dataset.github.io (CC BY-NC-SA 4.0 + Dataset Terms; Baidu link); repository github.com/GenImage-Dataset/GenImage (README news 2024-03-15: Google Drive folder).
5. c2pa-python, github.com/contentauth/c2pa-python (Apache-2.0 and MIT).
6. ASVspoof 2019, arXiv:1911.01601; doi:10.7488/ds/2555 (ODC Attribution).
7. AASIST, github.com/clovaai/aasist (NAVER, MIT-style).
8. FaceForensics++, github.com/ondyari/FaceForensics; Terms of Use (non-commercial).
9. IPTC Digital Source Type vocabulary, cv.iptc.org/newscodes/digitalsourcetype.
10. Müller et al., Interspeech 2022, arXiv:2203.16263; In-the-Wild project page (Apache-2.0 statement) and huggingface.co/datasets/mueller91/In-The-Wild (cc-by-sa-4.0).
