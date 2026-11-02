I didn't find any blocking bugs. The repo is ready for a **private** push, as long as the push names exactly which refs to send (finding 1). The earlier engine-integration gap is closed for the paths that were actually run (finding 2). This review was read-only: I ran nothing, so test, Ruff and pip results are as you reported them.

## Findings

**1. Medium (publication risk): push with explicit refs, not `--mirror` or `--all`.**
- The repo has tool checkpoint refs: `.git/refs/codex/turn-diffs/checkpoints/...` and `.../captures/.../base`. Both point to `2ebb77a`, which is not in `master`'s reflog, so it is probably a snapshot of uncommitted work. `git push --mirror` would upload it to GitHub.
- The tag `litmus-text-before-multimodal-2026-10-26`, which `README.md:10` references, is only sent if you push it explicitly.
- The local branch is `master`. There's no remote and no local `main`.
- **Recommendation:** push only `master` and that tag, e.g. `git push -u origin master` plus `git push origin refs/tags/litmus-text-before-multimodal-2026-10-26`. Decide on purpose which name the default branch should have.
- I can't tell whether "all reachable refs" in `history_audit.json:2` included the `refs/codex/*` commit. Either confirm it did, or keep those refs off the remote.

**2. Low: the engine check only covers the "no flag" path.**
- The text score was 1.0039, above the 0.9272 threshold, so the result was `no_signal` (`ui_engine_reports.json:41`). The flagging branch was never exercised over HTTP.
- `README.md:280` says this "closes the engine-integration gap". That is true for model loading, the profile match, applying calibration and serializing the report. It does not cover a flagged result.
- **Recommendation:** add a short qualifier, e.g. "for the not-flagged path". It isn't a blocker; the flag logic sits in frozen, unit-tested scorer code.

**3. Low: `--verify-saved` checks less than it could** (`scripts/verify_ui_engines.py:14-44`).
- In saved mode it never compares `report["input"]["sha256"]` to `synthetic_input_sha256`. The hash is only checked before submitting in a live run (`:99-102`).
- It doesn't assert `result == "no_signal"` or the `calibration_artifact_sha256`/`threshold_c` values.
- For C2PA it doesn't check the fixture hash, `policy == "production"`, `declared_ai_use == "declared"` or the trust-list sha256.
- The checks it does make are correct, and I confirmed the saved values by hand against `eval/results/r1f/preflight_a.json`. All of these fields match: scoring_config, hash, score, nll, xent and scored_window.
- **Recommendation:** add those assertions.

**4. Low: the script saves reports before validating them** (`verify_ui_engines.py:115-118`). A failed run overwrites the saved evidence with failing reports. `--verify-saved` would catch that later, but writing after `validate()` (or to a temp name, then renaming) is cleaner.

**5. Low (privacy accounting): the audit lists authors only.** `history_audit.json:18-20` shows only `ryan.j.bush0@gmail.com`. Committer and tagger identities aren't enumerated. This is fine for a private repo; check them before any public release. The Windows username and paths in `fresh_install.json` and older evidence are already disclosed in `GITHUB-PUBLICATION.md:24-27`.

**6. Informational: the shipped lexicons still say the license is pending.** The `src/litmus/quality/lexicons/*.txt:4` headers say `license: OPEN — pending`, and they ship in the wheel. The README and decisions note that MIT supersedes this, but a wheel-only recipient sees only `LICENSE`. That is acceptable under MIT; a one-line note in `INSTALL.md` would be enough if you want one later.

**7. Informational: build setup is unpinned.** `pyproject.toml:2` has `requires = ["setuptools"]` with no minimum, while the SPDX `license = "MIT"` + `license-files` format needs setuptools ≥77. pip's isolated build normally fetches a current version, so this is fine in practice. The wheel was built with `--no-build-isolation`, so a fresh-machine build path wasn't tested; that is already disclosed.

## What I checked and found correct
- **License files:** `LICENSE` is the standard MIT text. `pyproject.toml` license metadata and package data look correct, and no new dependencies were added.
- **`.gitattributes`:** the new lines only add the publication paths and the new script. I couldn't view the diff, so I can't confirm nothing else changed.
- **INSTALL.md:** the commands and paths exist (`__main__.py`, `quality.txt`, `download_models.py`, `Start-Litmus.cmd`, the cu124 extra index in `requirements.lock`). The CPU, profile, download and private-access caveats are accurate.
- **Report consistency:** both CUDA reports are byte-identical in content and match the frozen preflight and calibration. The C2PA report matches the expected policy result: valid integrity and signature, unknown trust, no timestamp, zero anchors.
- **Polling loop:** a job starts as `running` (`server.py:59`), so the script's poll loop works.
- **Scope statements:** `GITHUB-PUBLICATION.md`, the README and the decisions entry describe their limits honestly and don't claim a public deployment.

## Readiness
Ready for the private push, provided you use explicit refspecs (finding 1). Findings 2–7 are optional polish.

## Not inspected or tested
- I ran nothing: no tests, Ruff, pip check, build, git commands or the science verifier.
- I didn't view the `.gitattributes`/README/pyproject diffs against HEAD, only the current files.
- I didn't check what commit `2ebb77a` contains, or which refs the audit actually enumerated.
- I didn't review the blob contents behind the audit, `verify_wheel_r1.py`, the rest of `server.py`, the static UI, or the GitHub repo and visibility settings.
