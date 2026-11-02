# R1-G evidence and review handoff

Authority: Ryan approved R1-G-PLAN.md at8afab9e,G0–G5. Source/policy
b5cdc56d14a063d56683d825cef7c7ecdaac69b4 committed before first test intent;
unchanged afterward. Frozen source047421c and accepted freezebf45565 remain
distinct. All48 accepted E/F evidence/scientific files and frozen source/quality/
lexicon/explicit historical E reconciliation maps pass byte identity checks.

## Checks actually run

Existing .venv/Scripts/python.exe, inside selected suite:
`-m pytest -q --tb=short --ignore=tests/test_offline_guards.py
--ignore=tests/test_offline_c2pa.py --ignore=tests/test_c2pa_d1.py
--ignore=tests/test_c2pa_d2.py --ignore=tests/test_c2pa_d2_worker.py
--ignore=tests/test_c2pa_d3.py` → **587 passed,21 deselected in26.54s**.
Outside from C:/Users/Ryano used absolute interpreter/test/ignore paths and the
same options → **587 passed,21 deselected in17.84s**.

After final scorer-window assertion/error-receipt changes, focused
`-m pytest tests/test_evaluation_metrics.py tests/test_evaluation_gate.py
tests/test_evaluation_journal.py tests/test_evaluation_run.py -q --tb=short`
→ **48 passed in1.41s** inside. Outside absolute paths,order gate/journal/metrics/
run → **48 passed in1.43s**. Initial sandbox temp denial resolved with authorized
pytest access; no installation. These targeted checks supplement the broader
suite, not a claim of a later full-default rerun.

`-m ruff check .` → **All checks passed!**
`-m pip check` → **No broken requirements found.**
`git diff --check` and staged whitespace → **exit0**, ordinary CRLF notices only.
Strict UTF-8/source audit → **PASS**,zero replacement characters; source digests
in r1g_implementation_audit.json. Focused tests cover CLI/help and import isolation
(evaluator import loads neither torch nor transformers).

Approved actual operations, each via scripts/evaluate_r1g.py:

- `preflight` → exit0/PASS, exact assets/full CUDA hash/synthetic result,zero test
  opens/blocks;wall28.0820951s.
- `score` → exit0,all3,361 valid,one attempt/read each,zero failures/aborts/pending/
  retries/recovery/blocks. No test performance inspected before complete pass.
  Count-only journal/activity diagnostics confirmed advancing slow progress.
- `verify` → exit0,complete ledger verification PASS.
- `metrics` → exit0,112 clean/60 paired slices,locked1,000 shared group draws,
  multiplicity,full-precision intervals/statuses saved.
- `verify-results` → exit0,independent expanded-rank/arm/rate reassembly PASS for
  every saved metric/interval,without text/model access.
- Separate actual pairwise AUROC(455,625 comparisons),direct metadata parent-join/
  flag/outcome oracles → PASS. Commit timestamp precedes first intent; initial
  source audit matches final header. All accepted frozen bytes remain unchanged.

Seventeen scientific files,total19,937,414 bytes,under eval/results/r1g/.
SHA-256 map/resources in eval/results/r1g_verification.json. Header binds accepted
freeze/artifact/source/data/reconciliation,G code/policy,full versions/profile,
test projection. No raw texts/tokens/logits/weights in Git.

## Results, omissions and limits

675 groups,675 humans,675 clean machines,2,011 attacks;100% valid coverage.
AUROC0.8035775034293553;TPR448/675;observed FPR31/675,separate from Fdev14/298.
README/full metrics publish intervals/paired denominators;homoglyph58/675 versus
clean448/675. Missing14 paraphrases remain missing;one window no-op retained.
Overall replicates all defined;88 clean cells/one paired slice suppress intervals.

Scoring wall5,303.18972689996s/CPU4,966.84375s exceeded15–30min estimate;cause not
profiled,no gate relaxation. GPU peak allocated5,854,253,568 bytes,reserved
6,188,695,552. Metrics29.8144554s;independent reassembly24.844619s.
Local CUDA exact profile only;no hardware portability/native-isolation claim.
Prepared RAID train.csv source groups,not official test/unseen-generator protocol.
Conditional bootstrap excludes calibration uncertainty;correlated slices,
contamination risk,language proxy,first512 tokens. Original E cumulative transfer
compliance remains **unproven**,not rehabilitated by this run.

Not run: six ignored live-network/native-C2PA modules,whole slow suite21 tests,
real test-text repeats(prohibited),CPU fallback/calibration,1% calibration,
tuning/recalibration/reselection,new wheel/GPU portability,network/acquisition,
new dependencies,UI/later scope. Earlier D/F reviews remain reviewer-reported.

Evidence confidence B: target/regression checks,complete actual run and independent
formula reconstruction;external validity/native isolation remain bounded limits.
**Submitted for independent review,not R1-G closure.**
