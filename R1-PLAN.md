# Litmus R1 implementation plan — DRAFT v2 FOR REVIEW (not approved)

Baseline: R0 closed at `13f6a2d` (reviewer-verified by ChatGPT/Codex: 96 tests passing from outside the repository, Ruff clean, Git clean). Governing documents: `SPEC.md` v0.3 + Addenda A/B. This plan proposes resolutions for the items Addendum B left OPEN before R1, then defines checkpoints. **Nothing here is approved; R1 work starts only after Ryan approves this plan (and each gated item below).** Docker isolation remains **not run**. R2–R4 remain deferred.

Evidence marking: **VERIFIED (date, source)** = checked by the plan author against the stated source on 2026-10-27; **REVIEWER-VERIFIED** = checked by Codex; **PROPOSED**; **OPEN**; **ESTIMATE**.

---

## 1. Decisions to resolve before R1 code

### 1.1 Text model pair and execution profile — PROPOSED

| Role | Model | Revision (pin) | License |
|---|---|---|---|
| Observer | `Qwen/Qwen2.5-0.5B` | `060db6499f32faf8b98477b0a26969ef7d8b9987` | Apache-2.0 |
| Performer | `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604adf67be50417f59c2c2f167def9a775` | Apache-2.0 |

- **VERIFIED (Hugging Face model API):** both revisions above are the current `main` SHAs; both cards declare `apache-2.0`; both repos carry an identical `LICENSE` file (same Git blob); both `model.safetensors` are 988,097,824 bytes; `tokenizer.json` has the **same Git blob ID** (`443909a6…`) in both repos (and in the 1.5B pair). Same blob ID implies identical bytes; the SHA-256 is computed and recorded in R1-A.
- The 1.5B pair is **not** used in R1 (one model pair means one calibration; avoids D4/D11 complexity). Reconsider after R1.
- **Execution profile:** primary = CUDA on the RTX 4060 Laptop GPU, fp32 weights, float32 log-softmax and reductions, batch size 1. The profile is part of the calibration hash (§1.2). **CPU fp32 is an uncalibrated fallback**: on CPU the detector returns `inconclusive` (`no calibration for this configuration`) unless a separate CPU calibration is produced through the full R1-F procedure.
- **New dependencies requiring Ryan's approval (gated, R1-A):** `torch` and `transformers`, exact versions pinned in the lock file. Candidate: `torch==2.6.0` from the official cu124 index (a `cp313`/`win_amd64` wheel exists, VERIFIED earlier from the PyTorch index); the `transformers` version is chosen in R1-A by `pip check` plus a real two-model forward pass. Compatibility is not assumed.

### 1.2 Calibration identity and source hashes (resolves Addendum B5) — PROPOSED, strict matching

`scoring_config_hash` = SHA-256 of canonical JSON (UTF-8, sorted keys, no insignificant whitespace) containing exactly:

1. **Addendum A4 fields:** `scorer_version`, `formula_id`, observer/performer repo + commit, `tokenizer_json_sha256`, `add_special_tokens`, `split_special_tokens`, `truncation_side`, `max_tokens`, `min_tokens`, `weight_dtype`, `reduction_dtype`, `score_direction`, plus `preprocessing_version`.
2. **Numerical execution profile:** device type (`cuda`/`cpu`); GPU name; NVIDIA driver version (`"unavailable"` if lookup fails — a distinct value, so it does not match a calibrated profile); CUDA runtime reported by torch; `torch` and `transformers` versions; `torch.backends.cuda.matmul.allow_tf32`, `torch.backends.cudnn.allow_tf32`, `torch.get_float32_matmul_precision()`; deterministic-algorithm setting; OS family.
3. **Source identity:** `source_sha256` = SHA-256 over the sorted list of `path + "\n" + sha256(file bytes after CRLF→LF)` for a fixed file list covering the scorer, model/tokenizer loader, scorer configuration, and text preprocessing/decoding path (initially `src/litmus/scorer/binoculars.py`, `src/litmus/scorer/loader.py`, `src/litmus/scorer/tokenize.py`, `src/litmus/config.py`, and the text-decoding module in `src/litmus/ingestion`); the file list itself is a hash input. LF normalization applies only to these files and is documented in `docs/interfaces.md`.

**Strict matching in R1:** a calibration applies only when the runtime `scoring_config_hash` equals the calibration's. Any difference — including driver, library version, device, or source change — yields `inconclusive` with reason `no calibration for this configuration`. **No probe-based reuse across profiles.** Consequence: updating the driver, torch, or transformers invalidates the calibration until R1-F is rerun.

### 1.3 RAID sampling and generator quotas (resolves Addendum B3) — PROPOSED

- **VERIFIED (RAID dataset card):** license MIT; `source_id` is the UUID of the human-written source text; RAID-train domains are News, Books, Abstracts, Reviews, Reddit, Recipes, Wikipedia, Poetry; RAID-extra domains are Code, Czech, German; 11 LLMs and 12 attacks; train is 802 MB without and 11.8 GB with adversarial rows.
- **Domain allowlist:** the eight RAID-train domains above. **Excluded explicitly:** the entire RAID-extra split (Code, Czech, German) and any row whose `domain` is not in the allowlist. Per-row language is not verified; residual non-English rows in allowed domains are a stated limitation.
- **Deterministic, source-unique quota assignment** (all inputs: seed, dataset revision, metadata only):
  1. Eligible source = has one clean human row and ≥1 clean machine row (`attack = none`) in an allowed domain.
  2. Cells = (domain, generator) pairs present among eligible rows, sorted lexicographically. Cell quota q = ⌊N_target / #cells⌋; the remainder is added one per cell in sorted order.
  3. Within each domain, order eligible `source_id`s by SHA-256(seed ‖ `source_id`).
  4. Round-robin over cells in sorted order: assign to the cell the next unassigned `source_id` (in hash order) that has a clean row from that cell's generator. **Each `source_id` is assigned to at most one cell** (source-unique).
  5. If a source has several clean rows for that generator (decoding × repetition penalty), select the row with the smallest SHA-256(seed ‖ row `id`).
  6. A cell that runs out of sources stops; shortfall is recorded. No reallocation (keeps the procedure simple and reproducible).
  7. Split is independent of cell: dev if SHA-256(seed ‖ `source_id`) falls in the first 30% of the key space, else test.
- Attacked rows (`paraphrase`, `homoglyph`, `zero_width_space`; exact labels verified in R1-E) are included only for selected clean machine rows (`adv_source_id` link), obtained by streaming the full file with a metadata filter; rows scanned and ordering-bias notes recorded.
- **N_target is set from the synthetic runtime benchmark (R1-B2), before selection;** the selection and manifest are committed only after N is fixed.
- **1% calibration disabled** (≈300 dev negatives < 1,000 minimum); only the 5% calibration may be created.
- **Downloads are gated:** RAID acquisition needs Ryan's approval at R1-E.

### 1.4 C2PA settings validation and fixture strategy — PROPOSED

- **VERIFIED (c2pa-python 0.38.0 wheel source, the version in the R0 venv):** settings are applied with `Settings.set(path, value)` (or `Settings.from_dict` / `from_json` / `update`) and attached through `Context`/`ContextBuilder.with_settings`; `Reader.get_validation_state()`; `Builder.set_no_embed()`; a builder remote-URL binding exists (`c2pa_builder_set_remote_url`).
- **R0 finding preserved (reviewer-verified at R0-B):** the installed library **silently accepts unknown setting keys**. Therefore a setting "accepted" is not evidence that it takes effect. Offline behavior of the C2PA analyzer is established only by the loopback trap test **with a passing positive control**; until both pass, the C2PA analyzer stays disabled.
- **Fixtures generated locally** by a committed script with `Builder` and a locally generated **test CA hierarchy** (`cryptography` already present as a c2pa dependency): trusted signer, untrusted signer, no manifest, tampered bytes (integrity invalid), active `trainedAlgorithmicMedia` declaration, ingredient-only declaration, and a remote-reference asset (`set_no_embed` + remote URL at the loopback trap) for the trap test and positive control (fetch enabled, `allowed_network_hosts` = trap address only).
- **Test trust anchors are separate from production:** the test CA lives only under `tests/fixtures/c2pa/` and is loaded only by tests; production configuration never references it, enforced by a test asserting the production trust list contains no test anchor.
- **Risk (UNVERIFIED):** C2PA may reject self-generated certificates lacking required profile fields. Fallback: c2pa-python repository test certificates after a license check; otherwise affected rules use constructed library outputs, labeled as such. `not_checked` states use constructed outputs if no real fixture produces them.
- Ordered rule table (Addendum A2): one test per rule plus an ordering test.

**Limitation — empty production trust list in R1:** with no trusted anchors, every valid manifest gets `signer_trust = unknown`. **No C2PA result can be `supports_ai` in R1**; valid AI-use declarations are reported as `inconclusive` / `untrusted_signed_ai_declaration` (rule 8). The README and every report state this. Adopting a production trust list is OPEN (post-R1).

### 1.5 Retired scorer math and tests — OPEN (Ryan's decision)

Options:
- **(a) Approve read-only consultation (recommended):** the builder may read retired files via `git show litmus-text-before-multimodal-2026-10-26:<path>` and port the Addendum A4 math and its hand-computed test vectors into new files, citing the source commit in the commit message. No file is restored or checked out.
- **(b) Decline:** implement A4 from the spec alone, with **no** reading of retired-repository material. Note that the toy-parity evidence (`docs/evidence/toy-parity.md`) existed only in the retired tree and was removed in the cleanup; under (b) it is not consulted. Validation instead uses the pinned upstream reference (Binoculars commit `c8ae2f9`, read from the upstream repository) and fresh hand-computed vectors. Slower; no dependency on retired code.

Codex recommends (a), with fresh scalar-oracle validation; the decision is Ryan's.

Either way, the new implementation must pass an independent scalar oracle written fresh in R1-B.

## 2. Checkpoints (each ends with a commit, full pytest + Ruff, clean Git, and independent review)

| ID | Scope | Gate / approval | Done when |
|---|---|---|---|
| R1-A | Pin and install `torch`/`transformers`; download the pinned Qwen pair by setup command; tokenizer checks (SHA-256, full vocab equality, `add_special_tokens`/`split_special_tokens`, literal special tokens); offline load with HF trap test (A1.4.2) + positive control | Approval request below | Models load from local files only; trap zero connections with passing control; tokenizer results committed |
| R1-B1 | Scorer per Addendum A4 (decision 1.5); validation guards; `scoring_config_hash` per §1.2 with strict matching; CPU = uncalibrated | Decision 1.5 | Hand-computed and fresh scalar-oracle tests pass; real-model smoke test on synthetic text records the execution profile and hash |
| R1-B2 | Synthetic runtime benchmark (no RAID data) on the primary profile, through the production scorer | — | Measured throughput and peak memory committed; **N_target fixed** from it |
| R1-C | Text quality observers (SPEC §8.3): versioned lexicons; unit/metamorphic/span tests | — | Observers never affect origin results (test) |
| R1-D | C2PA analyzer per §1.4: fixture script, rule table, trap + positive control, test/production trust separation | — | All 10 rules tested; trap claims reported separately from isolation claims; empty-trust-list limitation in report |
| R1-E | RAID data prep per §1.3 and Addendum A3 using the fixed N_target: allowlist, deterministic source-unique quotas, dedup, cleanup, manifest. **No scoring.** | Ryan approves RAID acquisition at this point | Manifest committed with counts, shortfalls, exclusions, seed, revision, hashes |
| R1-F | Dev scoring; 5% calibration bound to `scoring_config_hash`; freeze record | — | Freeze committed **before** any test scoring |
| R1-G | Single test scoring; grouped paired bootstrap; SPEC §10 metrics | Reviewer confirms the freeze first | Results with counts, CIs, insufficient-data labels; README results section |
| R1-H | Local UI on 127.0.0.1; loopback UI test; reasons, limitations, "not a probability" | — | UI smoke test without models; manual run with screenshots |

**Effort (ESTIMATE):** 25–40 focused hours, per SPEC; R1-A, R1-D, and R1-E carry the most uncertainty (downloads, certificate behavior, data volume).

## 3. Approvals

**Requested now (one consolidated request):** see `R1-APPROVAL-REQUEST.md`: the plan, R1-A dependencies and model download, and decision 1.5.

**Deferred:** RAID acquisition (approved separately at R1-E, after N_target is fixed).

## 4. Explicitly excluded from R1

Image ML detection, audio, video, PDF/DOCX, OCR, the 1.5B pair, cross-modal fusion, deployment beyond local, Docker installation or image pulls, CI workflows, and any restoration of retired files.
