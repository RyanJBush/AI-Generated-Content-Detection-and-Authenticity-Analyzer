# Litmus catch-up review and checkpoint checklists

Prepared from Ryan's catch-up note. Builder checkout, installation state, device inventory, and benchmark results have not been independently inspected here. This document sets review requirements; it does not mark tasks complete.

## Baseline and source checks

The local v0.3 spec hash matches Ryan's supplied SHA-256 exactly: `6829a54da03ecde1b535afda9fbb771f491cb6abe326a8b84435689c9a08a7ac`. The local original build-plan hash also matches: `4f49c015bdd9ef4d20669c43222bb3722f76e4f2e22cc595802eaa4da8fb87fc`. The differently named v0_3_1 attachment and builder checkout were not supplied; their equivalence/progress remains reported by Ryan.

Pinned [upstream metrics](https://github.com/ahans30/Binoculars/blob/c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8/binoculars/metrics.py) support the shifted numerator, all-position denominator, and token-ID-mask concern. Claude's reported direct-execution toy results are consistent with that code. I have not independently rerun Claude's toy script or verified its exact numerical outputs. Keep its script, seed, environment, and raw output as evidence; exact fp32 toy parity does not establish bf16/fp16/backend parity.

## Findings: accept, qualify, or dispute

| Item | Disposition | Reason / v0.3.2 treatment |
|---|---|---|
| B1: strict fingerprint vs deployment | Accept the design tension; qualify the proposed remedy | A changed profile is intentionally incompatible under v0.3; no_calibration is correct rather than an app bug. It is not inevitable for every Space: compatible execution or separate calibration is possible. Split identity from profile for clarity, retaining strict combined matching until Ryan resolves D11. Twenty synthetic probes are drift screening, not a low-FPR validation study. |
| B2: evaluation budget | Accept | v0.3 added implementation and verification work while retaining 2.5 h. Use one fixed-file/config hashing mechanism, one guard, an append-only run log, and one-pass deduplication. D12 stays Open. Recommend measuring/re-estimating before choosing +1 h from buffer or deferring optional slices/plots. Do not silently drop uncertainty correctness. |
| C1: AUROC ties | Accept | Pairwise machine-positive AUROC awards an exact tie 0.5. No score jitter or arbitrary near-tie epsilon. An all-tied length baseline can yield AUROC 0.5 and conservative-threshold TPR 0. With 512 input tokens, the scored-target count is normally 511. |
| C2: dedup iteration/no-op attacks | Accept | Under delete-only cleanup, removing records cannot create new collisions. Compute the union of cross-group raw/token collisions, propagate pair removals once, assert invariants. Count byte-identical and retained-token-identical attacks separately; keep them in the primary declared population. |
| C3: literal special tokens | Accept measurement; do not automatically enable splitting | add_special_tokens=False prevents automatic insertion, not necessarily recognition of literal reserved strings. Probe actual Qwen fast/slow behavior at pinned versions. split_special_tokens=True changes the scoring input and may be version-dependent; treat it as a deliberate identity change if adopted. No silent stripping or rewriting. |
| C4: default vs True/False | Accept | Upstream calls its tokenizer without an explicit add_special_tokens override. Check omitted/default, True, False on ordinary and reserved/Unicode fixtures. Document any deviation instead of assuming equal IDs. |
| C5: truncation wording | Accept | Use one statement: right truncation retains the first 512 input tokens. Keep counts before truncation, after truncation, and scored targets distinct. |

[PyTorch numerical-accuracy guidance](https://docs.pytorch.org/docs/stable/notes/numerical_accuracy.html) warns against assuming bitwise identity across platforms/releases and CPU/GPU operations. Shared fp32 weights remove one source of variation; they do not prove threshold equivalence. [Transformers tokenizer documentation](https://huggingface.co/docs/transformers/main_classes/tokenizer) describes literal-special-token splitting separately from automatic special-token insertion. The actual selected Qwen implementation still needs the requested probes.

The concern about a Windows CPU-only torch installation is worth checking, but a generic installation command alone does not prove which wheel was installed. Use the [official PyTorch installation selector and verification](https://pytorch.org/get-started/locally/) for the observed hardware/Python, plus the installed build and an actual tensor operation. A driver-reported CUDA capability is not the same thing as the installed PyTorch CUDA runtime.

## D11 remains Open: measurements that inform Ryan's choice

Task 1 should return:

- Feasible pair **and weight dtype**, peak memory, and latency at actual lengths through 512, including reductions; whether 0.5B fp32 fits locally and on an observed deployment profile.
- Fixed-corpus per-text NLL_perf, NLL_obs, XENT, and B for supported fp32 vs lower precision, CPU vs GPU at matching dtype when feasible, and repeated runs/batch composition. Include max/median absolute differences and nonfinite/unsupported/OOM cases.
- Real deployment resources/access and numerical settings when accessible. A CPU simulation on Windows is not evidence that a Linux Space ran successfully.
- Tokenization-policy results; token IDs must match before attributing a score difference solely to runtime precision.

Recommend the simplest profile that fits both evaluation and deployment. Keep strict matching as the default while D11 is Open. If Ryan selects portability, first approve the profile allowlist, tolerances, independent validation probes, and dev-only threshold-crossing audit or deployment-profile recalibration. Task 1 pilot results must be rerun through Task 2's tested scorer. Do not select tolerances from held-out test behavior or call the same exploratory pilot an independent validation.

Synthetic probes alone cannot settle operating-point preservation: tiny score drift near a threshold can change labels. Before threshold reuse, report original/deployment label crossings for each relevant threshold on development data, including near-threshold texts, and resulting dev FPR/TPR. This is development evidence, not a guarantee of unchanged test FPR. If no deployment evidence is available, state D11 cannot yet be closed.

## D12 remains Open: measurements that inform Ryan's choice

Task 1 should return actual elapsed effort, setup/download time, remaining budget, measured full-path throughput, clean/dev/test/attack count projections, data-access/scanning constraints, and a short remaining-work estimate for Block 4. Separate engineer/agent effort from machine wall time; do not simply divide document count by throughput and call it total project time.

Recommended options for Ryan: allocate +1 h from buffer while retaining safeguards, or explicitly reduce optional per-slice bootstrap/plot work before test access. Overall/paired CIs, undefined-metric honesty, baseline thresholds, source/pair integrity, and guarded fresh/cached test access remain. The exact-binomial helper is small with SciPy already planned; cutting it alone is unlikely to rescue an hour. If any boundary-FPR method is deferred, the degenerate bootstrap must not be sold as a zero-risk interval.

Keep the current required outputs until Ryan records the choice. A tiny sample can still be statistically weak even if its runtime fits. D12 must be resolved before Block 4 and predeclared before the final test.

## Correction report: short review checklist (before Task 1 resumes)

- [ ] **Roles fixed everywhere:** SPEC §5, CLAUDE.md, AGENTS.md, decisions agree: Claude Code builds every block including evaluation; ChatGPT plans/reviews A/B/C/final; Claude optional. No swap-builder rows or mandatory per-block PRs remain. D11/D12 still Open.
- [ ] **Baseline and diff:** source v0.3/v0_3_1 hash, current edited hash, and lineage recorded without claiming edited bytes still equal the source. Supply changed files/diff and repository path.
- [ ] **Isolated interpreter/install:** show sys.executable, Python version, environment prefix, python -m pip --version, working directory, exact install command/index, package versions, and install exit status. These point to the project .venv. Account for the earlier background job and its output before proceeding.
- [ ] **Observed hardware/backend:** actual OS/CPU/RAM/disk plus GPU inventory/VRAM/driver, torch.__version__, torch.version.cuda, and torch.cuda.is_available(). If available, show actual GPU tensor allocation/computation. NVIDIA-present/CUDA-unavailable is an unresolved intended-GPU benchmark blocker, not a silent CPU fallback.
- [ ] **Clean baseline commit:** show repository root, git status, baseline commit identity/changed-file summary, and relevant instruction-file content. Initialize only the intended new repository if it is not already tracked. Do not claim a commit from a prose summary alone.
- [ ] **Stop point respected:** no tokenizer benchmarks or RAID scoring before this correction report is reviewed. Output clearly distinguishes executed checks from planned ones.

Review outcome: pass only the inspected evidence, list explicit missing/failing items, then resume the already scoped Task 1 when the correction report supports it. Do not restart the project or overwrite existing work.

## Checkpoint A: short handoff checklist (before Task 2)

- [ ] **Reproducible evidence:** commit/diff, exact commands and exit codes, benchmark/tokenizer/drift scripts, saved JSON, and representative raw terminal output. Numeric tables can be regenerated from those artifacts; unsupported or not-run cells are explicit.
- [ ] **Backend and measurement isolation:** redacted client/server configuration and provider-reported model tag confirm the claimed builder route as far as observable. Inspect active local model jobs and memory baseline; do not infer an empty GPU from a cloud model tag. No simultaneous installs/benchmark workloads.
- [ ] **Tokenizer C3/C4:** pinned revisions/hashes, ordinary and literal-special/Unicode fixtures, omitted/default vs True/False IDs/masks, split setting behavior/support, and final proposed policy. No unannounced input normalization or chat templates.
- [ ] **Benchmark code inspection:** actual two-model PyTorch/Transformers execution; all-real-position denominator and shifted numerator; full output vocabulary; float32 reductions; eval/inference mode; actual dtype/device and batch lengths. No generate call, truncated vocabulary, mocked logits, imported timing constants, or swapping in Ollama model outputs.
- [ ] **Timing/memory integrity:** accelerator synchronization; warmup separate from load/download; CPU threads and inference flags recorded; framework peaks and whole-device/host memory distinguished. Include actual max-length runs or explicit failure; do not extrapolate 512-token feasibility solely from short inputs.
- [ ] **Drift/proposal:** per-text statistics plus max/median deltas and nonfinite/repeat results, pair/dtype recommendation, actual deployment evidence or marked absence, and proposed sample counts within the complete inference budget. D11 remains Open until Ryan chooses; no borrowed labels authorized by synthetic drift alone.
- [ ] **Budget and boundaries:** elapsed/remaining effort and itemized Block 4 estimate support D12 options. No final calibration, held-out RAID outputs, test access record claiming unseen data without evidence, or invented deployment success.
- [ ] **Ready for math review:** include Claude's upstream toy script/output if available. Task 2 will create independent hand-computed expected-value tests; a builder self-test or upstream parity test is not independent mathematical validation.

Checkpoint A can support the pure-logits math work in Task 2 with D11/D12 still Open: neither decision changes the specified numerator/denominator. Resolve any contradictory tokenization/scoring requirements before dependent real-model behavior. D11 blocks final calibration/profile reuse; D12 blocks final Block 4 scope/budget. Explicit failure to access the deployment host is an open limitation, not an automatic blocker to pure math tests.

## Plan addendum and safe handoff

Use SPEC-v0.3.2.md for the changes above. The supplied diff is against the verified v0.3, **not** the builder's already edited SPEC.md. Ryan subsequently authorized conditional replacement: compare the working spec with the byte-verified v0.3/v0_3_1 baseline; if differences are exclusively the expected §5 role changes and D11/D12 rows, replace it with the verified v0.3.2. Otherwise show the unexpected differences. Verify the resulting canonical SPEC.md hash before recording adoption. Preserve decisions/history and distinguish the source attachment name from the canonical repository file.

The original build plan remains a baseline, with this addendum overriding only: actual builder-backend description, §5 staffing, the explicit Task 0 correction-report stop, tokenizer C3/C4, D11 drift measurements, simplified duplicate cleanup/run logging, and D12 provisional budget. Task 2 still retires the provisional benchmark math in favor of one verified production scorer. This addendum does not authorize extra features or claim any checkpoint has passed.

To the builder: finish the already requested correction report first. Once reviewed, complete Task 1 and return the checkpoint A evidence above. Record the actual model route; avoid identifying the implementer as Claude solely because Claude Code is the client. Keep all local work within the intended repository/environment and leave human decision rows Open.

## Integrity incident addendum: claims recorded before evidence

Ryan reports commit `a9a83dc` recorded adoption of v0.3.2 before the actual update occurred. The checkout/commit has not been independently inspected in this chat. The correction report has not been reviewed yet. The new reported upstream-parity evidence package remains fp32 CPU upstream-parity evidence; it does not verify the builder's code, installation, or benchmark results.

Treat this as a material provenance failure, not proof of intent or of every other claim being false. Builder summaries and committed decision prose are now claims requiring corroboration. Apply the checks below to existing Task 0 claims and later checkpoints regardless of backend. A commit proves that particular bytes were recorded, not that the event described in them happened. A different builder model does not remove this requirement.

### Add to the correction-report checklist

- [ ] Show `a9a83dc` and the new corrective commit. Correct with a follow-up commit that names the erroneous assertion and its actual state; do not rewrite the earlier history or label an unfinished action verified. If adoption is still blocked, say so.
- [ ] For spec adoption, show the canonical repository root/path, existence of `SPEC.md`, actual SHA-256, and the verified source SHA-256. The approved v0.3.2 source hash is `4b04892d65585d4c8d8ba9f07bd6fda3225ac1c8e76350d0dce217d8d6816aec`. A missing source file named SPEC-v0_3_2.md alone does not prove the canonical SPEC.md is wrong; inspect/hash SPEC.md itself.
- [ ] Attach the pre-replacement baseline diff establishing the authorized condition, then the actual replacement result. If that earlier diff was not retained, mark it unavailable; do not reconstruct and present it as an execution log. Verify current contents independently and disclose the missing historical evidence.
- [ ] Re-read §5 roles and D11/D12 in the resulting SPEC.md and AGENTS.md/CLAUDE.md; show that the file belongs to the claimed commit, not only an uncommitted working copy. Explain any difference between approved source bytes and committed/working bytes, including line-ending normalization.
- [ ] Add a compact claim/evidence table: claim, status (planned/attempted/verified/failed/not run), exact command and exit status, artifact path/hash, and commit/blob identity where relevant. Verify first; only then update the decision record. Do not include the decision file's own final hash inside itself.
- [ ] Explain the long-running shell with process/session identity, purpose, active children/work, output/log location, and whether it is idle or executing. Account for installer completion/failure and its target environment. Age alone is not evidence that it is hung, installing, or using model memory. Do not blindly terminate an unidentified process.
- [ ] Ryan independently checks repository history, canonical spec hash, and one environment command from the intended .venv before accepting correction. Missing or inconsistent evidence means correction remains unaccepted; it does not authorize rolling onward.

### Add to checkpoint A

- [ ] Pin the handoff to an exact commit and disclose uncommitted changes. Supply a claim/evidence table covering spec adoption, environment/device, tokenizer checks, throughput/memory, drift, and hosting. No prospective completion language in a verified-status row.
- [ ] Existence/hashes corroborate artifact identity, not correctness. Inspect benchmark/tokenizer source and personally rerun one bounded selected-pair smoke case plus the environment audit. Ensure reported values are generated by the submitted code rather than copied or hard-coded. Do not require a second expensive full benchmark solely for ceremony.
- [ ] Distinguish byte hashes, Git blob IDs, and Git commit IDs. Ryan compares the working tree to the handoff commit and verifies any environment-dependent byte changes; an echoed expected hash is not an independently computed hash.
- [ ] Check that raw logs and JSON agree on device, dtype, model revisions, lengths, counts, elapsed time, run command, and exit status. Preserve failed/not-run cells. Logs are corroboration and reproducibility aids, not incontrovertible proof of execution.
- [ ] Ensure artifact/decision chronology is stated honestly: execute → check outcome/file contents → record result → commit → hand off. An unsuccessful command or absent artifact cannot be converted to verified by a later narrative. UTC timestamps alone do not prove this sequence.
- [ ] Resolve the reported false adoption claim and account for the unknown background activity before accepting numerical benchmark claims. D11/D12 remain Open unless Ryan explicitly records decisions.

### Backend recommendation

Recommend moving Tasks 1–2 to an actual Claude-backed builder session if Ryan already has access, preserving the repository and having that session audit Task 0 before adding work. This is a project risk/time recommendation based on observed handoff failures, not a controlled ranking proving Gemma is worse or Claude error-free. The existing upstream toy package is useful review evidence but does not certify a new scorer implementation.

Gemma may continue with narrowly bounded, reversible tasks if each is independently checked. If Ryan retains it for Task 1, require acceptance of the correction report first, then one small verified step per handoff. Do not give it unattended scorer/calibration/evaluation responsibility on the current evidence. For Task 2, require independent inspection of role/shift/mask/final-position tests and hand-computed expected values before accepting it, whichever backend builds it.

When switching, verify effective provider/model routing rather than only changing a displayed name; the Ollama-compatible endpoint can still route a Claude Code client to non-Claude models. Start with a short factual handoff listing current commit, verified files, failures, open D11/D12, and unreviewed claims. Do not let a switch turn prior claims into accepted facts.
