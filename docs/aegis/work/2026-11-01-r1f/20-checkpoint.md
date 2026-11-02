# R1-F execution checkpoint

Current closure: Ryan supplied independent F review and confirmed freeze commit
bf455659053cca15ec82cb85065613c6b7459a44; R1-F CLOSED, reviewer-reported.
All execution/pending-commit notes below are historical. Frozen bytes preserved.
R1-G-PLAN.md is proposed only; no test access/scoring or active sessions.

Baseline clean master 3f3e787e02417e1f848812ba1aba956ad88bc95e.
State: F0/F1 committed at 047421cf4c36f8a946453eacc1b9c056bf5147d6;
source tree confirmed clean before execution. Hashed implementation sources
are frozen. Both fresh CUDA preflights66980/83284 passed and exact full scientific
comparison passed (fields/hash/source/assets/synthetic statistics/window).
Development score-dev23557 completed PASS: all1484 rows; elapsed274.489s,
CPU253.984s, GPU peak allocated5854253568/reserved6188695552 bytes, guards0/0.
Fresh first-ten-human audit17822 passed exact comparison; verify-dev passed.
Freeze assembly passed; all1484 valid,298 negatives,0 failures; c=-0.9272342324256897
in r=-B (14 above,1 tie). Artifact/application replay of all298 stored human scores
passed (14 strict flags,1 unflagged tie), reports round-trip; guards0/0.
No active execution sessions. All hashed sources remain at047421c.

Freeze payload SHA48035a7984482a325349b32b746a3463534089849254141da61a2a019ce228aa;
artifact file SHAedd84087ab56d25d43df653cdaaaa2f06dccdb196108c32c67c9e1a505822134.
Remaining: finish data/evidence-only checks/docs; commit metadata/artifact/freeze;
run verify-freeze for committed Git proof, read back clean status, report actual
source/freeze commits and stop independent review. No G scoring authorization.

Actual configuration hash from preflight A:
10f0fa316fa5f3d87c7819f86f09ecedc5bc5b1b71e9250d8586aece7390db2f.
Primary profile complete, driver572.60/CUDA12.4, GPU RTX4060Laptop, initialization
order false; guards connections0/forbidden-data0. Synthetic512 score1.0038838386535645.

- Calibration/application, dev-only guard, exact E/source reconciliation,
  journal/resume/tail recovery, artifact/freeze validation implemented.
- Full offline selection excluding six network/C2PA-control files:
  539 passed/21 deselected inside16.90s, outside15.32s. Unicode audit exposed
  encoding drift in a rewritten test fixture/docs; repaired explicit UTF-8 and
  escaped e-acute, targeted scoring identity tests61 passed2.35s after repair.
  Production sources unchanged since full regressions. Ruff clean, pip check clean;
  source audit10 files,1 existing docstring finding,0 violations. Whitespace clean.
- E preparation/model/formula/loader/config/tokenizer sources and scientific
  evidence unchanged. New normalized scorer source list has nine paths.
- Stable implementation commit: 047421cf4c36f8a946453eacc1b9c056bf5147d6.
  NEVER edit hashed code while retaining scores; stop on actual failures.

Execution order after stable commit:
1. scripts/calibrate_r1f.py preflight --output eval/results/r1f/preflight_a.json
2. Separate fresh process preflight --output eval/results/r1f/preflight_b.json
3. score-dev (defaults primary directory, both preflights exact compared)
4. Fresh audit-dev --output eval/results/r1f/dev_repeat_audit.json
5. verify-dev --output eval/results/r1f/dev_verified.json
6. freeze --output eval/freezes/r1f_freeze.json (artifact name derives exact hash)
7. Update actual docs/evidence only; stage/verify artifact and freeze; commit.
8. verify-freeze after commit (read-only Git blob proof), report source/freeze hashes,
   exact checks/N/c/configuration, not-run checks and stop for independent review.

Use existing .venv, fresh processes and approved primary CUDA only. Guarded code
reads only allowed dev blobs under data/, never raw CSV, SQLite or test blobs.
Model-free helpers may read all committed metadata for manifest verification.
Any actual stop condition: preserve failure receipt/journal, stop scoring; no
silent repairs, CPU fallback, rescore under changed source or artifact publication.
