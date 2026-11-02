# R1-F execution checkpoint

Baseline clean master 3f3e787e02417e1f848812ba1aba956ad88bc95e.
State: F0/F1 implementation/tests ready for stable source commit; NO CUDA/model
checks or real development scoring have started. No active execution sessions.

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
- Before scoring: commit all source/tests/interfaces/approval and implementation
  evidence. Confirm clean source tree and HEAD. Then NEVER edit hashed code while
  retaining scores. Record actual source SHA here in a later evidence-only update.

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
