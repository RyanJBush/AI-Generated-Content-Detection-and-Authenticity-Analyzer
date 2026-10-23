# SPEC.md — Litmus: AI-Text Likelihood + Slop-Pattern Analyzer

Status: DRAFT v0.3.2 — incorporates accepted review corrections to v0.3; D11 and D12 remain Open for Ryan. Task 1 gathers evidence; checkpoint A review precedes Task 2. Do not treat this revision as resolution of those decisions.

Baseline provenance: v0.3 SHA-256 `6829a54da03ecde1b535afda9fbb771f491cb6abe326a8b84435689c9a08a7ac`; original build-plan SHA-256 `4f49c015bdd9ef4d20669c43222bb3722f76e4f2e22cc595802eaa4da8fb87fc`. Ryan reports SPEC-v0_3_1.md is byte-identical to that v0.3. This revision is derived from the matching v0.3, not from an independently inspected builder checkout. Repository edits produce a new hash; record lineage and the edited hash separately.
Owner / final decision-maker: Ryan (human). AI agents propose; Ryan decides disputes.
Time budget: 10–12 focused hours, MVP only.

Markers used in this document:
- **UNVERIFIED** — a factual assumption that must be checked in code or docs before relying on it.
- **DECISION** — a choice reviewers may challenge; record disagreements in §12.
- **REPORTED** — a finding from a reviewer (e.g., Codex) that the implementer must re-confirm before relying on it.

---

## 1. Goal

Build a working, tested, deployed tool that, for a given English text:

1. Produces a **Binoculars score** using an experimental re-implementation of Binoculars (Hans et al., ICML 2024, arXiv:2401.12070) adapted to a small Qwen2.5 model pair, calibrated and evaluated on a sample of the RAID benchmark (Dugan et al., ACL 2024, arXiv:2405.07940).
2. Produces an **explainable slop-pattern report**: highlighted spans for stock phrases, hedges, repeated word n-grams, and claim phrases to inspect, with per-feature counts.

What the outputs are and are not:
- The Binoculars score is a **ratio of performer mean negative log-likelihood to observer-to-performer cross-entropy**. It is **not** a probability that a text was machine-written, and it is not calibrated as one.
- Flags are produced by **thresholds calibrated on a development split for one specific model pair**. A text that falls between thresholds receives an **abstention** ("uncertain"), which is a policy choice, not a measurement of confidence.
- The tool reports evidence, not verdicts. It must never present output as proof that a person used AI.

## 2. Non-goals (excluded from MVP)

- Claiming a measured accuracy for "slop" or "content quality." No labeled ground truth exists in scope (see §7.3).
- Claiming that published Falcon-7B results transfer to the Qwen pair.
- Fine-tuning or training neural models.
- **Deferred:** Layer-B-only logistic regression, A+B combined logistic regression, per-decoding-strategy breakdowns.
- **Deferred Layer B features:** vague-claim judgments, MATTR / content-word ratio, rhythm (sentence-length CV), sentence-Jaccard repetition.
- **Deferred:** `synonym` attack (add only if time remains after §10 is met).
- LLM-as-judge layer (Ollama). Stretch only, after §10 is complete.
- Chat templates or instruction formatting of any kind around input text.
- Multilingual support, code detection, or text under 64 tokens.
- Submitting to the RAID leaderboard (test labels are hidden; out of scope).
- Browser extension, user accounts, database, REST API beyond what Gradio provides.
- Watermark detection.
- Hand-tuning thresholds, lexicons, preprocessing, or model choice after the test split has been scored (see §7.2 freeze).

## 3. Architecture

```
raw text ──► (no text-altering normalization; see §3.4) ──► tokenize once (shared raw-text tokenizer, no chat template)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
  Layer A: Binoculars scorer      Layer B: slop-pattern analyzer
  (observer=base, performer=instruct)  (rule-based, no model)
  → performer NLL, cross-entropy,      → spans[] on ORIGINAL offsets,
    B score, baselines                    feature counts, rates
          │                               │
          └───────────────┬───────────────┘
                          ▼
         Report object (dataclass / JSON) + configuration-specific calibration
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
         CLI (litmus score)      Gradio app (HF Spaces)
```

### 3.1 Layer A — Binoculars scorer

**Model pair (DECISION, experimental adaptation):**
- observer = `Qwen/Qwen2.5-1.5B` (base), performer = `Qwen/Qwen2.5-1.5B-Instruct`.
- Fallback pair: `Qwen/Qwen2.5-0.5B` (observer) / `Qwen/Qwen2.5-0.5B-Instruct` (performer).
- The reference implementation's defaults are a Falcon-7B base observer and Falcon-7B-Instruct performer. Results from that pair are not assumed to transfer.
- Every model and tokenizer is loaded at a **pinned commit revision**, recorded in `src/litmus/config.py` and in every report and cache key.

**Tokenizer compatibility (REPORTED + UNVERIFIED):**
- Codex reported identical `tokenizer.json` files across the 1.5B and 0.5B pairs, with differing EOS settings. The implementer must independently verify, at the pinned revisions:
  1. byte-identical `tokenizer.json` (record SHA-256 of each),
  2. identical vocabulary and identical `input_ids` on a fixed test corpus that includes non-ASCII, homoglyph, and zero-width characters,
  3. which special tokens (BOS/EOS) the tokenizer adds by default, and that both models emit the same output-logit dimension with identical token-ID interpretation. Compute cross-entropy over the full shared output dimension; do not trim to the number of tokenizer entries.
- Use **one** tokenizer (the observer's) for both models, with `add_special_tokens=False`, `padding_side="right"`, and `truncation_side="right"`. Raw text only; **no chat template, no system prompt, no automatically inserted BOS/EOS**. Right truncation retains the first 512 input tokens. The explicit MVP proposal is `split_special_tokens=False` (tokenizer default); literal reserved-token spellings may still encode to their reserved IDs. That is different from automatically adding tokens. Do not strip or silently rewrite them.
- Set an explicit pad token if none exists, and record it. All masking uses `attention_mask`, never `pad_token_id` comparison (see §12 item D2).
- **C3, Task 1 measurement:** at pinned tokenizer and library versions, record IDs, decoded token pieces, and attention masks for ordinary prose and literal `<|endoftext|>`, `<|im_end|>`, and `<|im_start|>` inside surrounding text. Compare `split_special_tokens=False` vs `True` if supported by the selected tokenizer implementation. Document unsupported options explicitly. Qwen behavior is UNVERIFIED until the actual probe output is reviewed. Changing the policy is a scorer-identity change and a documented reference deviation, not a silent fix.
- **C4, Task 1 measurement:** on the same corpus (also Unicode/attack-character cases), compare upstream-default tokenization, explicit `add_special_tokens=True`, and `False`. Record IDs and masks for each model tokenizer. If defaults/True differ from the proposed False policy, document the exact deviation; do not claim upstream input parity. Keep the intended policy frozen before calibration.

**Score definition (Qwen adaptation with reference positional behavior, DECISION):**

Pinned upstream reference: [ahans30/Binoculars, commit c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8](https://github.com/ahans30/Binoculars/tree/c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8). The role assignment and positional averaging below were checked against that commit's `binoculars/detector.py` and `binoculars/metrics.py`. This project follows those positional conventions, while deliberately replacing token-ID-based padding detection with attention masks and using float32 log-softmax/reductions. It is not a bitwise reproduction of the upstream implementation. Record these differences in `docs/method.md`.

For one right-padded input `x_1 … x_T`, let `a_t` be its attention mask. Logits at input position `t` predict the next token. Define `O_t = log_softmax(observer_logits_t)` and `P_t = log_softmax(performer_logits_t)` over the full shared output dimension, at temperature 1.

- Numerator positions: `t = 1 … T−1`, with `m_t = a_t · a_{t+1}`. The first input token has no preceding prediction and is not a target. With required right padding, this equals the upstream shifted-target attention mask.
  `NLL_perf = [Σ_(t=1)^(T−1) m_t · (−P_t[x_{t+1}])] / [Σ_(t=1)^(T−1) m_t]`
- Denominator positions: **all non-padding input positions**, `t = 1 … T`, with `d_t = a_t`.
  `XENT = [Σ_(t=1)^T d_t · Σ_v exp(O_t[v]) · (−P_t[v])] / [Σ_(t=1)^T d_t]`
- The denominator includes the final real input position's next-token distribution, even though there is no observed next-token target there. This is intentional reference behavior. Do not restrict it to numerator positions.
- `B = NLL_perf / XENT`. Lower B is the predeclared machine-positive direction. B is unitless; both terms use natural logs. It is not a likelihood ratio or an authorship probability.
- `n_tokens` is the untruncated input-token count; `n_input_tokens` is the retained non-padding count (at most 512); `n_scored_tokens` is the numerator target count (normally `n_input_tokens − 1`). Denominator count is `n_input_tokens`.

Use toy logits whose final-position cross-entropy differs from earlier positions to test this positional convention independently of the role-assignment test.

**Implementation rules:**
- `torch.inference_mode()`, `model.eval()`, max 512 input tokens; **right truncation retains the first 512 input tokens**; record `truncated` and `n_scored_tokens`.
- Compute in float32 for the log-softmax and reductions even if model weights run in bf16/fp16; record weight dtype.
- Reject inputs with fewer than 64 original input tokens (report `too_short`, with null score/statistics). Do not fabricate zero scores for unavailable values. For valid inputs, require finite NLL/XENT/B and positive XENT; numerical failure returns an explicit error, not a flag.

**Thresholds and calibration (D11 Open):**
- Fit thresholds on **clean human dev rows only**; keep attacked rows out of calibration. Every detector/baseline has its own thresholds and recorded score direction (§7.2).
- Distinguish **scoring identity** from the **execution profile**. `scoring_identity_hash` covers model IDs/revisions; tokenizer files, implementation/settings including special-token handling; max length; positional/masking rules; float32 reduction policy; and the fixed scorer/config/preprocessing source-file hashes. `execution_profile_hash` covers model weight dtype, device/backend/attention implementation and relevant numerical flags, plus dependency-lock/package-build identities. Record fuller environment details (OS, hardware, driver, versions) for reproducibility. Exclude timestamps, host-specific absolute paths, and unrelated builder files from numerical identities.
- **Unresolved-policy default:** preserve v0.3's strict compatibility by computing `scoring_config_hash` from canonical JSON containing both identity hashes. Calibration remains keyed by this full hash. Differing weight dtype or execution profile does **not** automatically inherit thresholds, even if scoring identity matches. D11 may later authorize a documented alternative; this spec does not choose it for Ryan.
- Store the calibration artifact at `calibration/<scoring_config_hash>.json`, including identity/profile hashes, clean-dev manifest hash, human/source-group counts, thresholds for every detector at both target FPRs, achieved dev FPRs, and threshold-selection rule. CLI/app verify compatibility before labels. Missing/incompatible calibration gives raw scores with `no_calibration`.
- **D11 option A:** keep strict matching and calibrate/evaluate/demo with a compatible selected profile, or produce separate calibration/measurement artifacts per execution profile. Sharing pair and fp32 weight dtype reduces one difference but does not, by itself, prove CPU/GPU/library equivalence.
- **D11 option B:** allow a finite list of explicitly validated deployment profiles for the same scoring identity, with an auditable compatibility receipt. About 20 fixed synthetic probes can screen numerical drift; they cannot establish unchanged FPR or population equivalence. Tolerances and an independent validation corpus must be specified before a validation comparison, not selected to make a candidate pass. Initial Task 1 pilot differences may inform a proposed tolerance but are not themselves an independent passing validation. Collect same-text, same-token per-text differences for NLL_perf, NLL_obs, XENT, and B; max/median errors, nonfinite counts, and repeated-run/batch effects. Before any threshold reuse, also check threshold crossings and actual FPR/TPR differences on **dev-only** data, including near-threshold examples, or recalibrate on clean dev for that deployment profile. This comparison is development evidence; final test remains untouched. Missing actual deployment-profile evidence is not a passing portability check.
- Task 1's drift evidence uses provisional diagnostic math and must be rerun through the verified production scorer after Task 2 and before calibration/profile approval. Tolerances, field matching, deployment-profile policy, and Ryan's D11 choice must be recorded before final calibration/freeze. Never infer approved compatibility from an Open decision.
- The published Falcon thresholds are not used. Baseline thresholds are evaluation artifacts, not additional app authorship flags. Numerical score caches always retain exact execution-profile identity; approving threshold portability must not cause cache values from different profiles to be mixed.

**Baselines (computed from the same forward passes, no extra model cost):**
- Performer-only mean NLL (the numerator alone).
- Observer-only mean NLL.
- Length-only (scored-token count) — sanity floor.

### 3.2 Layer B — Slop-pattern analyzer (reduced for MVP)

Rule-based and deterministic. Runs on the **original text**; every flag maps to a `[start, end)` character span in the original string.

| Feature | Definition (DECISION) |
|---|---|
| Stock phrases | Case-insensitive, word-boundary matches against `data/lexicons/stock_phrases.txt`. |
| Hedges | Case-insensitive, word-boundary matches against `data/lexicons/hedges.txt`. |
| Repeated word n-grams | Lowercased word 3-grams (tokenized by a fixed regex) occurring ≥ 2 times; report every occurrence's span and the n-gram. |
| Claim phrases to inspect | Matches against `data/lexicons/inspect_phrases.txt` (e.g., "studies show", "experts agree"). Displayed as "phrase to inspect." **Not** evidence that a claim is unsupported. |

Output per feature: count, rate per 100 words, spans. If an aggregate is displayed, it is labeled "pattern density (unvalidated heuristic)."

Lexicons are plain text, one entry per line, with a header comment stating source (author-written), version, and SHA-256 recorded in the freeze file (§7.2). No scraped or copyrighted lists.

### 3.3 Report object

```json
{
  "version": "0.3.2",
  "scorer_version": "…", "preprocessing_version": "…", "scoring_config_hash": "…", "scoring_identity_hash": "…", "execution_profile_hash": "…",
  "models": {"observer": "…@<rev>", "performer": "…@<rev>", "tokenizer_sha256": "…", "weight_dtype": "…"},
  "n_tokens": 0, "n_input_tokens": 0, "n_scored_tokens": 0, "truncated": false,
  "binoculars": {
    "nll_performer": 0.0, "xent": 0.0, "score": 0.0,
    "baselines": {"nll_observer": 0.0},
    "flag": "flagged|uncertain_abstain|not_flagged|no_calibration|too_short",
    "calibration": {"artifact_sha256": "…", "scoring_config_hash": "…", "scoring_identity_hash": "…", "execution_profile_hash": "…", "t_strict": 0.0, "t_primary": 0.0, "source": "clean human dev rows"},
    "note": "Score is a ratio of mean negative log-likelihood to cross-entropy, not a probability of AI authorship."
  },
  "slop": {"features": {"stock_phrases": {"count": 0, "rate": 0.0, "spans": [[0, 0]]}}},
  "disclaimer": "…"
}
```

**Flag policy (abstention):** with dev-calibrated `t_strict` (dev FPR ≈ 1%) and `t_primary` (dev FPR ≈ 5%), where `t_strict ≤ t_primary`:
- `B < t_strict` → `flagged`
- `t_strict ≤ B < t_primary` → `uncertain_abstain`
- `B ≥ t_primary` → `not_flagged` (wording: "score did not cross the calibrated threshold" — never "human-written").

The primary binary operating-point evaluation (§7.3) uses `B < t_primary`. App `flagged` uses the stricter threshold; evaluation tables must not label the 5% operating-point TPR as the app flagged rate. Report app flag/abstention coverage separately. `not_flagged` wording: "score did not cross the calibrated threshold". The illustrative JSON above is a scored report; unavailable statistics/calibration use null, never placeholder zeros.

### 3.4 Normalization and offsets

- MVP applies **no text-altering normalization** before either layer (no NFKC, no zero-width stripping, no homoglyph folding). Highlight offsets therefore index the original string directly.
- Consequence for attacks: homoglyph and zero-width-space attacks reach the tokenizer unmodified. Results on these attacks measure the **raw** detector, and the README must say so.
- If any normalization is added later, it must keep an offset map from normalized to original text, bump `preprocessing_version`, and be reported as a separate defense ablation (DECISION; see §12 item D3).

## 4. Repository layout

```
litmus/
  SPEC.md  CLAUDE.md  AGENTS.md  README.md  LICENSE  pyproject.toml  .gitignore
  src/litmus/
    __init__.py
    config.py          # pinned model/tokenizer revisions, versions
    binoculars.py      # Layer A math + model loading
    slop.py            # Layer B features
    report.py          # dataclasses, JSON serialization
    cli.py             # `litmus score FILE`
  calibration/<scoring_config_hash>.json
  app/app.py           # Gradio UI
  eval/
    benchmark.py       # early runtime benchmark (Block 1)
    sample_raid.py     # source-grouped sampling → data/eval/*.parquet
    score.py           # cached scoring; shared freeze guard before test model/cache access
    evaluate.py        # metrics, grouped bootstrap, tables, plots
    freeze.json        # immutable run freeze written before test scoring (§7.2)
    runs.jsonl         # append-only run/access/outcome provenance
    results/           # generated only; never hand-edited
  data/lexicons/  data/eval/ (gitignored)  data/cache/ (gitignored)
  docs/method.md  docs/limitations.md
  tests/
```

## 5. Responsibilities

| Role | Who | Scope |
|---|---|---|
| Spec owner / tiebreaker | Ryan | Decides open items, including D11/D12; records approvals and final choices. |
| Primary builder | Claude Code interface, using the backend recorded in docs/decisions.md | All blocks, including Block 4 evaluation. Use scoped commits; no mandatory branch/PR per block. |
| Planner / reviewer | ChatGPT / Codex | Planning and evidence-based review at checkpoints A (feasibility), B (scorer), C (pre-test evaluation), and final. |
| Optional second reviewer | Claude, separate chat | Independent second opinions when actually requested/performed; not an implementation dependency. |

Current builder route, **REPORTED by Ryan**: Claude Code → `ANTHROPIC_BASE_URL=http://localhost:11434` → Ollama cloud model tag `gemma4:31b-cloud`. Record client/server versions, model tag, provider-reported revision if available, and redacted routing evidence in `docs/decisions.md`. The interface name does not establish which model generated code. A claimed model identity or independent review is not verified by the code's quality or a self-identification response. Litmus's actual detector still loads the pinned Qwen pair in PyTorch/Transformers; the builder backend does not replace it.

Rules mirrored in CLAUDE.md and AGENTS.md:
1. Read SPEC.md and the active task before each block. Complete the active checkpoint handoff; resume after the corresponding review without repeated permission for routine work inside an authorized task.
2. Never report a metric, test result, runtime, or command output that was not actually produced. Distinguish passed, failed, not run, and unsupported.
3. Record deviations in the commit/handoff and §12. Keep D11/D12 Open until Ryan decides; attach measured evidence without inventing approval.
4. README numbers come only from generated evaluation artifacts. Synthetic/Ollama examples are development fixtures, not held-out evidence or ground-truth judgments.
5. Never score test or consume cached test scores unless the shared guard validates the frozen configuration. Rewriting the freeze after inspecting test results does not restore held-out status (§7.2).
6. Task 0 correction report precedes tokenizer/benchmark work in the current handoff. Run installs/benchmarks in the foreground with captured output: exact command, working directory, interpreter/environment, exit status, and saved output. Prior background jobs must be identified and accounted for before measuring; no concurrent installs or unrelated resident model jobs during benchmarks.

## 6. Build plan

| # | Block | Budget | Done when |
|---|---|---|---|
| 0 | Spec review (both agents) + Ryan's decisions | 0.75 h | §12 decisions recorded by Ryan; agreed spec revision committed. |
| 1 | Scaffold + early feasibility: environment/GPU audit; tokenizer C3/C4; runtime/memory for feasible pairs/dtypes; D11 drift probes; actual deployment feasibility; D12 revised effort estimate | 1.25 h baseline; report overrun | Actual artifacts and exact commands; recommended pair **and dtype**, sample/attack budget, and D11/D12 evidence. Checkpoint A review before Task 2; Open decisions are not silently resolved. |
| 2 | Layer A: `binoculars.py` + tests on synthetic logits, incl. asymmetric role test | 2.0 h | §8.1 tests pass; reference formula re-confirmed against pinned commit; CLI scores one file end-to-end locally. |
| 3 | Layer B (reduced): `slop.py` + lexicons + tests | 1.0 h | Every feature has unit + metamorphic tests (§8.2); span integrity verified. |
| 4 | Evaluation: grouped sampling, dev scoring + calibration, freeze, test scoring, evaluate; D12 sets final budget/scope | 2.5 h provisional, **D12 Open** | `eval/results/` generated by one command; primary metrics with grouped CIs, counts, paired adversarial results, failure cases. |
| 5 | Gradio app + HF Spaces deploy | 1.25 h | Public URL works on 3 sample texts with the deployed pair's own calibration; disclaimer visible. |
| 6 | README, docs/method.md, docs/limitations.md | 1.0 h | Results table, failure cases, citations, ethics statement, reference-variant note present. |
| — | Buffer before any D12 allocation | 1.0–2.0 h | D12 may allocate +1 h to Block 4; this consumes buffer and must not be counted twice. |

Stopping points: after Block 3 the CLI tool is usable; after Block 4 it is measured; after Block 5 it is deployed. Budgets are estimates, not measured completion times. D12 must be resolved before Block 4; do not claim the expanded evaluation still reliably fits 2.5 h.

**D12 minimal implementation proposal, accepted simplifications:** one deterministic SHA-256 implementation over canonical JSON config and a declared fixed file list (supporting identity/profile subhashes), one shared guard, and one append-only `eval/runs.jsonl`. Hash contents and relative paths; reject missing required files. Keep the manifest/run outputs out of code fingerprints to avoid circular hashes; bind their hashes separately. Log run ID, UTC timestamp, input hashes, access/start/end state, and outcome; preserve prior records. This is provenance, not a tamper-proof access-control system. One offline writer is sufficient; do not build a service or locking framework.

**D12 options for Ryan:** (A) allocate +1 h from buffer to Block 4, retaining current metrics/checks; or (B) explicitly defer optional slice bootstrap tables/plots and other pre-test scope, retaining overall and paired-attack CIs, valid/undefined metric handling, and a meaningful boundary-FPR interval/limitation. Exact binomial is recommended to retain because SciPy is already planned; removing it is not presumed to save an hour. Any alternative boundary method/deferral needs Ryan's explicit recorded choice. Until that choice, existing §7.3 and §8.4 requirements remain in force. Scope/interval deferrals must be frozen before test access.

## 7. Evaluation methodology

### 7.1 Data and sample size

- Source: RAID **train** split (labels available). The test split's labels are hidden and it is not used.
- **UNVERIFIED:** the full train CSV is ~11.8 GB. Block 4 must not download it wholesale unless necessary. Options: the non-adversarial `train_none.csv` plus a targeted path for attacked rows, or Hugging Face `datasets` streaming. The method used, rows scanned, and any ordering bias in the stream (e.g., rows grouped by domain/model) must be recorded in `manifest.json` and discussed in `docs/limitations.md`.
- **UNVERIFIED:** how human-written rows are labeled (e.g., `model == "human"`), the exact attack names in the `attack` field, and whether attacked variants exist for human texts as well as machine texts.
- Sample size: **~2,000 clean English documents** is an exploratory target (about 1,000 source groups, one human and one clean machine text per group). Additional paired attack rows consume the same inference budget and are counted separately. Final clean-core size and attack-pair targets are set in Block 1 so that all dev + test + attack scoring fits in **≤ 1.5 h wall time** (DECISION). Use external/synthetic pilot texts for runtime checks; never benchmark held-out candidates. No performance estimates are made before measurement.
- Filters: English domains only; at least 64 input tokens under the fixed raw-text tokenizer. Select one eligible human and one clean machine text from each retained source group; stratify machine selection by generator and groups by domain where feasible. Pair human/machine domain membership through the source. Report per-class domain/generator counts, realized quotas, and exclusions; do not adjust quotas using detector results.

### 7.2 Source groups, splits, and leakage control

Procedure, in this order:
1. **Build source groups before selecting variants.** Group by the human `source_id`; resolve attack parent links from `adv_source_id` to the parent row's `id` and inherit its source group. These relationships are transitive, not a concatenated `(source_id, adv_source_id)` key. Validate the pinned dataset's semantics and fail on conflicting ancestry. Exclude unresolved/orphan attack rows and report their count; never invent a group from a missing parent.
2. **Assign groups to splits** (approximately dev 30% / test 70%) with a documented stable seeded SHA-256 mapping of canonical group IDs. Do not use Python's process-randomized `hash()`. Record actual group/class counts.
3. **Select the balanced clean core and attack variants** within each split using predeclared metadata-only quotas (§7.1). Scanning/filtering held-out metadata and text for fixed eligibility/deduplication is permitted before freeze; detector scores and error inspection are not. Matched attack eligibility never changes the clean-core metric population.
4. **Check cross-group duplicates** on raw-text SHA-256 and retained token-ID sequence (first 512 tokens). Remove all selected rows participating in a cross-group collision and report losses by split/class/domain. If a clean-core pair loses either member, remove the pair; discard its dependent attack comparisons. Use one ordered pass over selected rows to identify all cross-group raw/token collisions, then one dependency-cleanup pass and invariant assertions. Removing rows without backfilling cannot create new collisions; repeated iteration is unnecessary. Do not backfill based on detector outputs. Record that near-duplicates and unknown pretraining overlap are residual risks.
5. **Rebuild eligible attack pairs** after filtering/deduplication. Each attack row must retain its exact eligible clean parent in the same split. For each attack, calculate clean and attacked metrics on identical pair IDs. Keep the full clean-core results separate; report exclusions and attack-induced short-input abstentions. Do not silently count unavailable scores as detections or non-detections. Attack score/TPR changes on scoreable pairs are conditional on scoreability; report their denominator. Count attacked texts byte-identical to their clean parent and, separately, those with identical retained token IDs after truncation. Retain these no-op pairs in the primary predeclared attack population and disclose them; do not silently remove them to make attacks look stronger.
6. **Run development diagnostics**, including clean ChatGPT-vs-corresponding-human AUROC, on dev only. AUROC ≤ 0.6 triggers an implementation audit, not tuning to pass a target. Freeze choices after this diagnostic; if the subset lacks both classes, mark it unavailable.
7. **Calibrate each detector separately.** Define machine-positive `r`: Binoculars `r = −B`; performer NLL `r = −NLL_perf`; observer NLL `r = −NLL_obs`. Length uses `r = direction × n_scored_tokens`, with direction selected by clean-dev AUROC only (choose +1 for an exact tie). Classify machine when `r > c`. For each target α in {0.01, 0.05}, choose the **smallest observed clean-human dev score c** for which `count(r_human > c) / H_dev ≤ α`. This conservative tie rule may attain less than the target FPR. Record direction, c, achieved dev FPR, counts, and rule for every detector. For Binoculars, `t = −c`, preserving `B < t` and `t_strict ≤ t_primary`. Never adjust thresholds or direction on test. With no eligible dev humans, calibration fails explicitly.
8. **Freeze before test scoring.** Write immutable run inputs in `eval/freeze.json`: complete scorer fingerprint (§3.1), calibration-file SHA-256, all detector directions/thresholds, lexicon hashes and Layer-B implementation identity, sampling/metric policy, sample-manifest SHA-256, dataset identity, seed, and relevant dependency identities. Manifest contains row/group/pair IDs, split assignments, exclusions, retained-text/token hashes, and class/domain counts; it excludes subsequently generated metrics to avoid circular hashing.
9. **Enforce a shared guard** in `score.py`, any CLI/helper that accesses test models or cached test scores, and `evaluate.py`. Validate freeze/config/calibration/manifest hashes **before** fresh test scoring or reading cached test scores. Record first test-score access and its outcome in append-only `eval/runs.jsonl`; preserve all earlier entries. Exact frozen reruns may reproduce artifacts; inspected test results may not be used to select a new configuration and still be called held-out. If a post-test bug requires changes, retain the earlier run and label reruns exploratory; use a genuinely uninspected, source-disjoint holdout for renewed confirmatory evaluation.

Record random seeds, immutable dataset revision (or URL plus content identity), row IDs, selected source groups, and pair membership in `eval/results/manifest.json`. Streaming may scan only a bounded portion; document its sampling frame and ordering limitations. A provenance freeze is an auditable control, not a guarantee against a developer bypassing it.

### 7.3 Metrics and claims

**Primary (claims allowed, on this sample only):**
- Overall **clean-set AUROC** on test, Binoculars vs. performer-only NLL vs. observer-only NLL vs. length-only. Use machine-positive scores and the Mann–Whitney convention: `AUROC = P(r_machine > r_human) + 0.5·P(r_machine = r_human)`. Exact ties contribute 0.5; do not jitter scores or apply an arbitrary near-tie tolerance. Heavily tied length scores may legitimately have AUROC 0.5 and TPR 0 at a conservative 5% dev-FPR threshold; report this without post-test orientation/threshold changes.
- At the **dev-targeted 5% FPR** threshold (`t_primary`), frozen: **TPR and the actual test FPR**, both with CIs.

**Exploratory (reported, labeled exploratory, no headline claims):**
- Dev-targeted 1% FPR threshold (`t_strict`): TPR and actual test FPR. Resolution is limited: with H human test documents, one false positive moves FPR by 1/H.
- Per-generator and per-domain slices: descriptive only. A slice size (e.g., n ≥ 30) is **not** treated as evidence of stability; every slice reports counts and CIs, and wide CIs are stated as such.
- Abstention band: coverage and flagged/not-flagged composition on test.

**Uncertainty:** 95% percentile CIs from 1,000 seeded source-group bootstrap replicates; include all retained rows/pairs of a sampled group with its multiplicity. Use identical group draws across detectors and clean/attack comparisons. Primary CIs are **conditional on the frozen calibration**; they do not include dev-threshold or model-selection uncertainty. Report paired bootstrap differences when claiming an advantage over a baseline.

For slice AUROC, a replicate without both classes is undefined: never replace it with 0.5 or zero. Report valid replicate count and valid fraction; predeclare a minimum valid fraction of 95% for an interval. If fewer qualify, or fewer than two source groups support a metric, show the estimate if defined and mark the interval unavailable.

Each clean-core human row belongs to a different source group (§7.1). In addition to bootstrap FPR intervals, report a 95% exact binomial interval on these human indicators, explicitly assuming independent sampled source groups. This interval remains non-degenerate with zero observed false positives (or all false positives). It does not generalize to attacked/multiple-human-per-group populations, nonrepresentative sampling, or calibration uncertainty. Do not present a degenerate boundary bootstrap interval as evidence of zero population risk.

Per-generator AUROC compares that generator's selected machine texts to the **human members of those same source pairs**; per-domain AUROC uses both clean classes in that domain. Report the precise reference set and both class counts. Unsupported slices have null metrics with a reason, not invented values.

**Counts:** every table reports n human documents, n machine documents, and n source groups for that split/slice.

| Layer | Question | Method | Claim allowed |
|---|---|---|---|
| A (Binoculars) | Separation on clean text? | Primary metrics above | "On our N-document, G-group RAID sample, clean-set AUROC = X [CI]; at a dev-calibrated 5% FPR threshold, test TPR = Y [CI] with test FPR = Z [CI]." |
| A baselines | Does the ratio add value over plain likelihood? | Same metrics for performer-only NLL, observer-only NLL, length-only | Relative comparison on this sample only. |
| A under attack | How much do attacks shift detection? | Paired evaluation (§7.4) | Paired change on this sample only. |
| B | Do features behave as specified? | Unit + metamorphic tests (§8.2); qualitative failure-case table | Behavioral correctness only. **No accuracy claim for "slop" and no AI-detection claim for Layer B in MVP.** |

### 7.4 Paired adversarial evaluation

- Attacks (DECISION): `paraphrase`, `homoglyph`, `zero_width_space`. Add `synonym` only if time permits. **UNVERIFIED:** exact attack labels in RAID.
- How the attack subset is obtained (which file/stream, filter on `attack` and `adv_source_id`) is documented in `manifest.json`.
- For each attacked document whose clean original is in the same split, compare at **unchanged frozen thresholds**:
  - detection rate (machine) or false-flag rate (human, if attacked human variants exist) — clean vs. attacked;
  - paired score shift `B_attacked − B_clean` (distribution + median).
- CIs via source-group bootstrap. If attacked human variants are unavailable, report only the machine-side TPR change and say FPR under attack was not measured.
- Because MVP does no normalization (§3.4), homoglyph and zero-width results describe the raw detector.

### 7.5 Required outputs in `eval/results/`

- `benchmark.json`, `tokenizer_checks.json`, `runtime_drift.json`, `metrics.json`, `metrics_by_slice.csv`, `adversarial_paired.csv`, `manifest.json`; provisional Task 1 measurements are labeled as such.
- `roc_overall.png`, `score_histograms.png`, `attack_score_shift.png`
- `failure_cases.md` (false positives with smallest B and false negatives with largest B at the primary frozen threshold; separate app-policy errors if shown; excerpts ≤ 300 chars each). Call these extreme-score errors, not calibrated-confidence errors.

## 8. Testing

### 8.1 Layer A (no model download in CI)

- **Hand-computed values:** on tiny synthetic logits (e.g., vocab 4, T = 4), `NLL_perf`, `XENT`, and `B` match hand-computed values to 1e-5.
- **Asymmetric role test:** with observer and performer logits deliberately different, assert the implementation matches the hand-computed value for the specified roles **and** differs from the value obtained with observer/performer swapped (catches swapped roles in either term).
- **Shift/position tests:** catch off-by-one numerator alignment; independently require the final real input position in denominator cross-entropy and exclude it as a numerator target. Pad additions must not introduce a denominator position.
- **Masking:** right-padding a batch does not change any document's scores; mask derives from `attention_mask`; a real EOS token id inside the text is scored, not masked.
- **Baselines:** performer-only NLL equals the numerator; observer-only NLL computed independently.
- **Tokenizer checks:** tokenizer/output-dimension mismatch assertions fire; input IDs match the explicit raw-text special-token policy, with no automatically inserted BOS/EOS. Literal reserved-token strings, C3/C4 probes, and right padding/truncation are covered. If a literal reserved ID is a real interior target, the attention mask must preserve it.
- **Too-short input** returns `too_short` and null statistics. Numerical failures return an explicit error and null score.
- **Integration (marked `slow`, local only):** two real model loads at pinned revisions score a fixed string; two runs agree within a recorded tolerance.

### 8.2 Layer B

- Unit tests per feature with exact expected counts and spans.
- Metamorphic tests use controlled fixtures with isolated insertion boundaries and non-overlapping lexicon entries. In those fixtures, one stock-phrase insertion adds exactly one match; sentence duplication adds the explicitly calculated repeated-3-gram occurrences; inserting "studies show" adds one inspect-phrase match without altering other lexicon features. These are fixture-specific assertions, not universal insertion properties.
- Span integrity: `text[start:end]` equals the matched surface string for every span, including texts containing emoji, zero-width characters, and homoglyphs.
- Robustness: empty string, very long single sentence, non-ASCII punctuation.

### 8.3 App

- Smoke test that `app.py` builds the interface without loading models (models injected or mocked).
- App refuses to show a flag when calibration is missing or its scorer fingerprint mismatches.

### 8.4 Evaluation controls (tiny fixtures, no model download)

- Per-detector threshold/direction tests cover tied AUROC (all tied = 0.5), conservative tied thresholds, distinct units, and fixed test behavior.
- Source/attack-parent fixture keeps relatives together; deduplication removes dependent comparisons without mismatching clean/attack pair IDs.
- Test-score/cache access fails before freeze and on changed config, code, calibration, or manifest; identical frozen reruns succeed.
- Cluster-bootstrap fixtures preserve group multiplicities and paired detector draws; undefined single-class AUROC is explicit; zero-FP exact-binomial bound is nonzero under the stated one-human-per-group assumptions.

## 9. Hardware and deployment

- Local baseline: Windows 11 laptop, hardware **unverified in this planning chat**. Show OS, exact Python executable/version, CPU/RAM, disk, and GPU/VRAM/driver inventory. `nvidia-smi` failure is not proof that no NVIDIA GPU exists; use OS inventory and diagnose missing tools/drivers.
- Use the project `.venv` explicitly for install and verification; record `sys.executable`, environment prefix, `python -m pip --version`, exact installation command/index, package versions, and exit status. Choose a supported PyTorch build from official installation guidance for the actual hardware/Python/driver. Do not infer CPU-only vs CUDA-enabled from a bare `pip install torch` command.
- Show `torch.__version__`, `torch.version.cuda`, `torch.cuda.is_available()`, device name/capability if accessible, and a small GPU tensor operation when applicable. If an NVIDIA device exists but CUDA is unavailable, stop intended GPU measurements, explain the mismatch, and correct it or obtain an explicit CPU-only choice; never silently label CPU timings GPU-feasible.
- Task 1 benchmarks use unrelated/synthetic pilot texts and an actual full-vocabulary reduction. Begin at batch 1/short inputs and increase toward 512 retained tokens. Measure feasible pair/dtype combinations, cold load separately from warmed inference, peak host memory and GPU memory with methods/units, and clean process baseline. Separate framework-allocated/reserved memory from whole-device inventory. Account for prior background installers and resident local model jobs; the cloud builder route alone does not establish uncontaminated memory.
- Synchronize asynchronous accelerator work before starting/stopping timing; include both models and reduction work, including any device transfer. Record actual weight dtype/device placement, autocast/TF32 flags and attention implementation. Skipped/OOM/unsupported candidates are explicit outcomes, not measured alternatives. Roughly 50 texts per feasible pair is a target, not a prerequisite to report infeasibility.
- **D11 measurements:** for 0.5B, determine whether fp32 fits and its latency/memory locally and on the prospective deployment profile if accessible. On the same fixed corpus, compare fp32 to supported lower precision on the available GPU, and CPU versus GPU with the same dtype when feasible. Record per-text NLL_perf/NLL_obs/XENT/B, max/median absolute differences, nonfinite counts, repeats and lengths, and which comparisons were unavailable. About 20 drift probes screen numerical changes only. Record actual hosting access/resources and whether a matching profile can be used; do not invent unobserved deployment outputs. Resolve D11 before final calibration/freeze; production-scorer drift checks follow Task 2.
- **D12 measurements:** report Task 0/1 elapsed human/agent and machine/download time separately, remaining budget, end-to-end docs/sec through both forward passes and reductions, projected dev/test/attack inference and data-scan costs, and an itemized estimate for remaining Block 4 work. Use a tiny local fixture/metadata inspection if useful; do not build Block 4 early or inspect held-out detector outputs. Ryan then chooses budget allocation or scope deferral before Block 4.
- Prefer one selected pair for evaluation and deployment (0.5B if necessary). D11 additionally governs dtype/profile compatibility; one shared pair alone is not sufficient. Account for roughly doubled weight memory in fp32 versus fp16; actual feasibility comes from measurements including activations/full-vocabulary tensors.
- Numerical cache key: raw-text SHA-256 plus exact `scoring_config_hash` (identity and execution profile). Derive labels from validated calibration; do not cache mutable flags as numerical evidence. Guard all test cache reads.
- Pin dependencies. Litmus's scorer requires no paid model API key; the separately configured cloud builder may have provider authentication and is not a runtime dependency of Litmus.

## 10. Success criteria (MVP is "done" when all hold)

1. `pip install -e .` and `pytest` pass on a clean clone; CI is green, including the asymmetric role test.
2. `litmus score sample.txt` prints a valid report JSON with pinned revisions.
3. One command regenerates every file in `eval/results/` from cached or fresh scores, and refuses test scoring without a matching freeze.
4. Results include Binoculars and all three baselines with primary metrics, grouped-bootstrap CIs, counts, actual test FPR at each frozen threshold, paired adversarial results, and failure cases — whether results are good or bad.
5. Public Hugging Face Space works, uses its own pair's calibration, and shows the disclaimer and the "not a probability" note.
6. README states method (reference-code variant), sample size and groups, results table, failure cases, limitations, citations, and ethics statement, with every number traceable to `eval/results/`.

Success is defined by correctness, reproducibility, and honest reporting — not by reaching a particular accuracy.

## 11. Limitations (to appear in README and docs/limitations.md)

- Detectors are known to degrade on unseen generators, different decoding settings, and adversarial edits (RAID paper). Results here cover one sample of one benchmark.
- RAID generators predate current frontier models; performance on newer models is unknown.
- The Qwen pair is an experimental adaptation; results are not comparable to published Falcon-7B numbers, and calibration does not transfer between pairs.
- The Binoculars score is not a probability of AI authorship; the uncertain band is an abstention policy.
- No text normalization: homoglyph and zero-width results describe the raw detector, not a defended one.
- Sampling may be biased by stream order or file choice (documented in the manifest).
- Short texts, non-native English writing, formulaic genres (recipes, abstracts), and memorized/famous text may produce false positives.
- Layer B is a heuristic pattern counter with no validated relationship to human judgments of quality; "phrases to inspect" are not evidence of unsupported claims.
- Ethics: the tool must not be used as the sole basis for academic, employment, or moderation decisions.

## 12. Open questions for reviewers — proposed resolutions (v0.3.2)

| # | Question (from v0.1) | Proposed resolution | Status |
|---|---|---|---|
| 1 | Binoculars equations and role assignment | Base observer / instruct performer; shifted performer NLL numerator, all-real-input-position cross-entropy denominator. Reference pinned in §3.1; attention-mask and float32 deviations explicit. Add independent role and final-position tests. | Proposed — awaiting Ryan |
| 2 | Qwen pair appropriateness and vocabulary | Keep as experimental adaptation. Independently verify tokenizer.json hashes, vocab, input_ids, special tokens at pinned revisions. Raw text, no chat template, no appended EOS. Separate calibration per pair. No transfer claims. | Proposed — awaiting Ryan |
| 3 | Sample size, split, slice stability | ~2,000 docs is exploratory; final N from Block 1 runtime. Dev 30 / test 70 by source group. Primary = clean AUROC + 5% FPR operating point with actual test FPR; 1% exploratory. Group bootstrap; report human/machine/group counts. Drop the "n < 30" stability rule; all slices descriptive. | Proposed — awaiting Ryan |
| 4 | Which attacks | `paraphrase`, `homoglyph`, `zero_width_space`; `synonym` only if time permits. Paired evaluation at frozen thresholds (§7.4). | Proposed — awaiting Ryan |
| 5 | Vague-claim heuristic | Cut from MVP. Keep "claim phrases to inspect" lexicon, labeled as non-evidence. | Proposed — awaiting Ryan |
| 6 | Leakage beyond source_id split | Group by human source and resolve attack-parent ancestry (not composite keys); deduplicate with pair cleanup; calibrate each detector on dev; guard fresh/cached test access with immutable freeze; diagnostic on dev only (§7.2). | Proposed — awaiting Ryan |
| 7 | Time budget; what to cut first | Already deferred: both logistic regressions, per-decoding slices, four Layer B features, synonym attack. If Block 4 still overruns, cut next in order: (a) `attack_score_shift.png`, (b) per-domain slices, (c) `zero_width_space` attack. Never cut: correctness tests, likelihood baselines, grouped evaluation, CIs, failure analysis. | Proposed — awaiting Ryan |

**Additional decisions raised through v0.3.2 (D-items):**

| # | Issue | Proposal | Status |
|---|---|---|---|
| D1 | Scoring roles and positional behavior | Follow pinned code positions: shifted numerator, all real input positions in denominator. Label Qwen adaptation with explicit attention-mask/float32 deviations (§3.1). | Proposed |
| D2 | The reference code sets pad = EOS when no pad token exists and passes `pad_token_id` to its entropy function; if masking compares ids, real EOS tokens could be masked | Mask by `attention_mask` only; document as a deliberate deviation; test it (§8.1). | Proposed |
| D3 | No normalization vs. homoglyph/zero-width attacks | MVP: no normalization; results describe raw detector. Normalized-defense ablation deferred. | Proposed |
| D4 | Deployment pair may differ from eval pair | If Space cannot run 1.5B, use 0.5B for both eval and deploy. | Proposed — depends on Block 1 |
| D5 | Attacked human variants may not exist in RAID | If absent, report only machine-side change under attack; state FPR-under-attack not measured. | Pending verification |
| D6 | Baseline calibration and tied scores | Separate dev-only direction/thresholds per detector; conservative empirical FPR rule (§7.2). | Proposed |
| D7 | Calibration/configuration compatibility | Distinguish scoring identity and execution profile; strict combined match remains the unresolved-policy default. D11 controls any relaxation. | Proposed; depends on D11 |
| D8 | Duplicate filtering can orphan attack comparisons | Remove dependent comparisons and rebuild exact matched pair IDs; report exclusions/scoreability. | Proposed |
| D9 | Boundary FPR and conditional uncertainty | Group bootstrap conditional on frozen calibration; exact-binomial human FPR interval only under stated source-group assumptions. | Proposed |
| D10 | Clean-core composition | One human/one machine per selected source group; attack rows counted and budgeted separately; metadata-only quotas. | Proposed |
| D11 | Calibration portability vs deployment execution profile (B1) | Task 1 supplies fit/speed, dtype/backend drift, and actual deployment evidence (§9). Ryan chooses strict compatible/separately calibrated profiles, or an explicitly validated allowlist under §3.1. Probes alone do not validate threshold portability. | **Open — Ryan decision** |
| D12 | Expanded Block 4 budget/scope (B2) | Task 1 supplies measured elapsed/remaining budget, full-path speed, data costs, and remaining effort estimate (§9). Ryan chooses +1 h from buffer or explicit pre-test scope reductions (§6). Current uncertainty safeguards remain until changed. | **Open — Ryan decision** |

Reviewer disagreements and resolutions are recorded below.

| # | Raised by | Issue | Resolution (Ryan) |
|---|---|---|---|
| | | | |

## 13. References

- Hans, A., et al. "Spotting LLMs With Binoculars: Zero-Shot Detection of Machine-Generated Text." ICML 2024. arXiv:2401.12070. Code: github.com/ahans30/Binoculars (reference commit c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8)
- Dugan, L., et al. "RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors." ACL 2024. arXiv:2405.07940. Data: github.com/liamdugan/raid
