# Litmus: Claude Code build checklist

Status: implementation handoff plan; tasks and checks below are planned, not completed.

## Goal and working arrangement

Build the bounded Litmus MVP described in `SPEC-v0.3.md`: a reproducible Qwen-based Binoculars adaptation, separate deterministic pattern highlights, a measured RAID evaluation, and a usable public demonstration if hosting is feasible. Correctness and honest measurements define success; no accuracy target is promised.

Ryan chooses project decisions. ChatGPT owns planning and technical review. Claude Code owns all implementation, including the evaluation harness. Claude provides optional independent reasoning/document review. Ollama is optional support for synthetic development fixtures and explanations; it is not a benchmark labeler, scorer replacement, or required dependency.

This arrangement supersedes SPEC §5's earlier assignment of the evaluation harness to ChatGPT. At kickoff, record this staffing change in the repository spec. Keep the scoring and evaluation requirements unchanged unless a concrete technical disagreement is documented and resolved.

## Architecture, stack, and baseline

- Architecture: raw text → shared tokenizer → base observer/instruct performer → statistics and validated calibration; original text → independent pattern matcher; structured report → CLI/Gradio.
- Stack: Python, PyTorch, Transformers, NumPy/SciPy, a small tabular/plotting stack, pytest, Ruff, and Gradio. Choose and record exact working versions during setup; do not install a broad collection of optional packages.
- Baseline/authority: Ryan's request to use ChatGPT for planning and Claude Code for building; `SPEC-v0.3.md`; its review notes; upstream Binoculars commit `c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8`.
- Compatibility boundary: match reference positional behavior, explicitly retain attention-mask/float32 deviations, pin model revisions, and bind calibration/cache artifacts to the scoring configuration. Public score semantics live in the spec, not in an alternate formula in the app.
- Verification: toy-logit math, source/pair fixtures, frozen-threshold evaluation, real-model smoke checks, and app/CLI readback. Actual outputs are recorded; planned checks are never called passing checks.
- Test posture: focused correctness and regression tests required by SPEC §8; this handoff does not impose a separate strict test-first process. TDD route: mode off, decision skipped for strict RED/GREEN ceremony, authority this planning request; numerical and leakage-control tests remain mandatory.

A durable checklist is useful because the scorer, calibration, cache, evaluator, and app must agree on one configuration and score contract. Code is necessary to compute the statistics and reports; the minimum implementation is the layout already defined in the spec. There is no existing project checkout established in this planning chat. Claude Code first inspects its selected project directory and any existing instructions/files before scaffolding.

## Scope and budget

Baseline budget: spec alignment 0.75 h; feasibility/scaffold 1.25 h; scorer 2 h; patterns 1 h; evaluation 2.5 h; app/deployment 1.25 h; documentation 1 h; buffer 1–2 h. Total: 10.75–11.75 focused hours, assuming downloads and scoring fit. Track elapsed time and report overruns honestly.

Keep the spec's deferred features deferred. Do not add neural training, a judge model, an external API, accounts, a database, or agent orchestration. Prefer one active checkout and one builder. Use commits as useful checkpoints; six separate PRs are unnecessary unless Ryan wants them.

If work already exists, reuse its clear owners instead of creating parallel scorers, validators, or report formats. There is no legacy runtime to retire in the greenfield plan. A temporary benchmark kernel must be retired in Task 2 when the benchmark switches to the tested production scorer.

## Task 0 — Align the repository and decisions (0.75 h)

**Files:** `SPEC.md`, `CLAUDE.md`, `AGENTS.md`, `docs/decisions.md`.

- [ ] Inspect the selected project directory and existing instructions; identify existing work and preserve unrelated changes.
- [ ] Copy the supplied v0.3 spec to the repository as `SPEC.md`, recording its identity. Record the updated staffing arrangement above.
- [ ] Summarize the intended reference positional convention, conservative per-detector threshold rule, one-human/one-machine clean core, and configuration-bound calibration.
- [ ] Put genuine contradictory requirements in a short decision list. Use the supplied spec as the proposed default, not an invitation to silently redesign it. Do not mark pending human decision fields approved on Ryan's behalf.
- [ ] Keep the two agent instruction files short: authoritative spec, exact task scope, no fabricated outputs, no test-set tuning, no model judge, and the handoff format below.

**Acceptance:** repository location and baseline are explicit; spec and roles agree; unresolved decisions are visible. Hardware/feasibility exploration can proceed while review questions are outstanding; dependent final implementation follows the resolved convention.

## Task 1 — Feasibility and minimal scaffold (1.25 h)

**Files:** `pyproject.toml`, `.gitignore`, `src/litmus/config.py`, `eval/benchmark.py`, `tests/test_tokenizer_compatibility.py` (local/model-assets mark as appropriate), `eval/results/benchmark.json`, `docs/feasibility.md`, basic CI.

- [ ] Inspect OS, available Python, CPU/RAM, GPU/backend/VRAM if available, free disk, existing environment and model caches. Report observed values; do not assume a CUDA GPU.
- [ ] Create an isolated project environment and minimal package skeleton. Resolve package versions compatible with the observed machine and record them. Do not alter global Python/system packages merely for convenience.
- [ ] Resolve immutable revisions for the proposed 0.5B and 1.5B base/instruct candidates. Verify tokenizer JSON hashes, IDs on adversarial-character fixtures, output dimensions, and explicit no-special-token/right-padding/right-truncation settings.
- [ ] Start with the smaller pair. Begin at batch size 1 and a short input, then use representative retained lengths up to 512. Measure both model forward passes **plus** the required float32 log-softmax and full-vocabulary cross-entropy reductions; forward-pass-only timing understates cost/memory.
- [ ] Separate download/load time, warmup, and steady-state scoring. Record lengths, batch size, device/backend, weight/reduction dtype, docs/sec, peak memory measurement method, and cold-start behavior where observable.
- [ ] Use synthetic or unrelated pilot texts only. Never benchmark future held-out RAID candidates. Aim for roughly 50 pilot texts per feasible pair; shorten a run or skip the larger pair with an explicit reason if resources/time make it infeasible. Never report skipped measurements as measured.
- [ ] Keep any temporary benchmark calculation isolated and marked provisional; replace it with the production scorer in Task 2. Benchmark scores are not detector-performance results.
- [ ] Check actual deployment eligibility and available resources for Ryan's account, using official documentation/account evidence available in that environment. Check a local Gradio launch as well. Identify costs or unavailable account access rather than assuming free compute.
- [ ] Recommend a single pair for both evaluation and demo. Estimate the complete dev/test/attack inference cost from measurements, include expected setup/data overhead separately, and propose clean-core and attack-pair counts. A changed sample target must be recorded before final sampling.

**Acceptance:** measured feasibility evidence, explicit unmeasured items, recommended pair/counts, and an initial install/import check. No full dataset evaluation yet.

**Review checkpoint A:** return Task 1's handoff to ChatGPT before committing to a large scoring run. This checkpoint is the end of the first Claude Code prompt.

## Task 2 — Scorer math, model adapter, and report/CLI (2 h)

**Files:** `src/litmus/binoculars.py`, `config.py`, `report.py`, `cli.py`, `tests/test_binoculars.py`, `docs/method.md`; update `eval/benchmark.py`.

- [ ] Implement a pure logits-to-statistics function independently of model loading. Performer NLL uses shifted observed targets; observer-to-performer cross-entropy includes all real input positions, including the last. Use attention masks and float32 log-softmax/reductions.
- [ ] Test hand-computed values, asymmetric roles, final-position inclusion, causal shift, right-padding invariance, real EOS IDs, short inputs, and nonfinite failures. Test the two NLL baselines and retained-length baseline.
- [ ] Add pinned model/tokenizer loading, raw-text tokenization, input counts/truncation, and output-dimension checks.
- [ ] Implement one report owner with explicit null unavailable values and version/config identity. CLI scores a file; without matching calibration it returns a raw score and no authorship flag.
- [ ] Route the benchmark through this scorer and retire the provisional kernel. Recheck the selected configuration's runtime/memory if production behavior changes the earlier estimate.

**Planned verification:** `python -m pytest tests/test_binoculars.py`; `python -m ruff check .`; a local marked real-model run; `litmus score sample.txt` with a fixed development fixture. Exact fixture/CLI options are documented once implemented.

**Acceptance:** demonstrated mathematical correctness, finite local real-model report, no unsupported labels, and no second math implementation in benchmark/app.

**Review checkpoint B:** send scorer diff, numerical fixtures/expected values, test output, one report JSON, and updated timings to ChatGPT. Resolve math issues before evaluation.

## Task 3 — Deterministic pattern features (1 h)

**Files:** `src/litmus/slop.py`, `data/lexicons/*.txt`, `tests/test_slop.py`; extend report fields.

- [ ] Implement stock phrases, hedges, repeated word 3-grams, and claim phrases to inspect only.
- [ ] Define word boundaries, word counting, overlap/count semantics, and per-100-word rates. Handle zero words without division by zero.
- [ ] Preserve original character offsets, including emoji, non-ASCII punctuation, zero-width characters, and case-insensitive matches. Do not highlight offsets from a lowercased copy without mapping.
- [ ] Add controlled-fixture unit/metamorphic tests and span readback assertions. Describe the inspect phrases as prompts for inspection, not unsupported-claim detection.

**Planned verification:** `python -m pytest tests/test_slop.py`; inspect sample highlighted spans against the original text.

**Acceptance:** counts/rates/spans have defined semantics and pass the required fixtures. No quality or authorship accuracy claim for Layer B.

## Task 4 — Sampling, calibration, freeze, and evaluation (2.5 h)

**Files:** `eval/sample_raid.py`, `eval/score.py`, `eval/evaluate.py`, small shared evaluation helpers if needed, `tests/test_evaluation.py`, `calibration/*.json`, `eval/freeze.json`, generated results.

- [ ] Inspect the pinned RAID schema on a bounded sample; confirm human labels, source/attack-parent semantics, exact attack names, data availability, and sampling frame. Document streaming scans/bias and download costs.
- [ ] Use the §7.2 procedure: stable source grouping and hash splits, metadata-only quotas, balanced source-paired clean core, cross-group raw/truncated deduplication, and dependent-pair cleanup. Keep attack pairs in the same split as the exact clean parent.
- [ ] Test on tiny synthetic tables first: ancestry, duplicates, dropped clean parents, short attacked variants, pair IDs, and realized counts.
- [ ] Score dev only, run diagnostics, and fit each baseline/detector direction and thresholds with the specified conservative tie rule. Test units/directions separately.
- [ ] Implement one shared configuration/freeze/calibration validator used by score generation, cache reads, evaluation, and app calibration loading where applicable. Include relevant fingerprints and an auditable first-test-access record; no elaborate access-control service is needed.
- [ ] Produce a pre-test run summary of fixed pair, sample/group counts, attack pairs, thresholds, fingerprints, and runtime estimate. Verify configuration and calibration compatibility before access.
- [ ] Run final test under the frozen configuration. Compute actual FPR/TPR, clean AUROC and baselines, paired attack changes, and predeclared descriptive slices. Group-bootstrap paired comparisons; identify conditional-calibration uncertainty, undefined slices, and boundary-FPR limits.
- [ ] Generate the spec's results files and failure excerpts directly from outputs. Preserve prior runs and label post-inspection corrections honestly.

**Planned verification:** `python -m pytest tests/test_evaluation.py`; a tiny end-to-end fixture run that checks freeze rejection before test access and success for an exact replay; one documented real regeneration command whose flags match the implemented tools.

**Review checkpoint C:** return the dev-only pre-test summary, control-test output, and evaluation diff to ChatGPT before the final test run. After review, execute the frozen run and return results for interpretation; favorable metrics are not an acceptance criterion.

**Acceptance:** traceable manifest/config/calibration, no source/pair leakage in fixtures or retained data, reproducible outputs, and honestly scoped metrics.

## Task 5 — Gradio app and usable demonstration (1.25 h)

**Files:** `app/app.py`, `tests/test_app.py`, deployment configuration, `docs/feasibility.md` updates.

- [ ] Use the same scorer/report/configuration/calibration as CLI/evaluation. Inject or mock model dependencies for lightweight interface tests.
- [ ] Show score semantics, actual model configuration, truncation, too-short/error states, raw-only output on calibration mismatch, abstention, and non-authoritative pattern highlights.
- [ ] Distinguish the app's strict flagged rate from the 5% binary evaluation operating point. Keep the disclaimer visible and input-text logging out of default behavior.
- [ ] Run three local sample texts plus short/error cases. Deploy using the verified hosting route when account access and requested publishing scope allow it; ask only for actual missing access or a paid-resource decision. Record a working public URL or a specific deployment blocker with local launch instructions. A local-only run does not satisfy the spec's public-demo success criterion.

**Planned verification:** app build smoke test with model injection; local browser report readback; public URL readback after deployment. Record observations, not guessed screenshots/latency.

**Acceptance:** the user-visible app agrees with CLI output and shows the selected pair's valid calibration. Public demonstration is verified, or clearly outstanding.

## Task 6 — README, final checks, and delivery (1 h)

**Files:** `README.md`, `docs/method.md`, `docs/limitations.md`, license/citation information, existing tests/CI.

- [ ] Explain setup, local app/CLI usage, evaluation regeneration, configuration identity, formulas/deviations, sample selection, measured runtime, result provenance, failure cases, and limitations.
- [ ] Link published numbers to generated results. Avoid detection-probability claims or transfer of Falcon results to Qwen.
- [ ] Run a clean-environment installation, complete appropriate tests/lint, and model-free CI checks. Reuse existing evidence unless a change invalidates it.
- [ ] Check an end-to-end user path from text input through report/highlights, plus a reproducible evaluation replay. Confirm no API secrets or raw evaluation dataset dumps are included in the Git repository.
- [ ] Supply repository status/commit identity, public demo if available, exact verification outputs, and remaining limitations. Keep incomplete criteria visibly incomplete.

**Final review:** ChatGPT reviews the README claims against artifacts and the final changes against the spec. Ryan owns final resume/project wording and release decisions.

## Overrun policy

Cut the attack-score-shift plot first, then per-domain slices, then one attack type; record the change before test access if it affects analysis. Keep formulas, likelihood baselines, source/pair controls, actual test FPR, uncertainty, and failure analysis. Reduce sample targets from measured runtime before freeze; do not select the sample size from favorable results. If the budget still fails, deliver the measured CLI milestone and state deployment or evaluation work remaining.

## Handoff after a review checkpoint

Return one compact report containing:

1. Task ID, repository path, branch/commit, and changed files or patch.
2. What was implemented or measured, with spec deviations.
3. Exact commands run, exit results, and relevant actual output/artifact paths.
4. Current elapsed time and measured hardware/runtime where relevant.
5. Remaining uncertainties and a proposed next task.

Pause at the explicitly named review checkpoint so Ryan can bring the report to ChatGPT. Routine implementation decisions within each task do not require repeated permission. Claude Code should not claim another agent independently reviewed work unless it actually happened.
