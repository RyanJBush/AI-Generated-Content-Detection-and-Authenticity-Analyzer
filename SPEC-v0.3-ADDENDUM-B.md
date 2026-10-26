# SPEC v0.3 — Addendum B: R0 approval corrections

Ryan approved **R0 only** on 2026-10-26, with the corrections below. Precedence: Addendum B > Addendum A > `SPEC.md` v0.3. R1 and later remain **unapproved**.

## B1. Scope control
`R0-PLAN.md` controls R0 scope. Deferred to R1: model loading, PyTorch/Transformers, tokenizer behavior and token-count boundaries (Addendum A6 rows for 64/512 tokens), and all R1 analyzer behavior. R0 analyzers are placeholders only.

## B2. Whitespace-only text (replaces the A6 row)
Whitespace-only text is accepted by ingestion and gets origin `result = inconclusive` with reason code `no_nonwhitespace_content` (not `too_short`). Quality observers (R1) report `none_found` with `rate_per_100_words = null`.

## B3. Corrections to A3 (R1 data preparation; recorded now, applied in R1)
- Seeded selection does **not** guarantee generator balance. R1 must either set explicit per-(domain × generator) quotas, or select without generator quotas and report the observed generator distribution. Which one: **OPEN (decide before R1)**.
- Dataset-row eligibility must not use filename extensions (RAID rows are not files). Row text must decode as valid text and pass the NUL and control-character rules (v0.3 §6.1, steps 2b–2c); the extension rule applies only to files given to the CLI.

## B4. Offline evidence: positive control and claim types (adds to A1.4)
- **Positive control:** any trap-based test must have a paired control in which network access is deliberately permitted to the loopback trap (e.g., C2PA with remote fetch enabled and `allowed_network_hosts` containing only the trap address). The control must show the trap **receives** a connection. If the control fails, the paired "zero connections" result is invalid (the fixture or trap cannot detect attempts) and is reported as such.
- **Two different claims, reported separately:**
  1. *Passes under network isolation* (e.g., `docker --network none`): the code does not **depend** on network access. It does **not** show that no connection was attempted.
  2. *Zero attempted connections observed* (trap test with a passing positive control): no attempt reached the trap for that fixture and configuration. It does not cover other destinations or code paths.
- If no remote-reference C2PA fixture can be produced in R0, both the trap test and its control are "not run," and the C2PA analyzer stays disabled.

## B5. Unresolved before R1
The calibration design is **OPEN** and must be resolved before any R1 scorer or calibration code:
- which execution-profile fields (device, dtype handling, library/driver versions) are hashed versus recorded only;
- whether and how scorer **source code** hashes (and which files, with which line-ending rule) enter the scoring-config hash.
Addendum A4's field list stands as a provisional proposal only.

## B6. R0 environment rules
- Install only `pytest`, `ruff`, `Pillow`, `c2pa-python` into the project `.venv`; pin versions in a lock file.
- Docker: use only if already installed; otherwise local isolation testing is "not run." Do not install Docker. Do not create or publish CI workflows.
- No model downloads, dataset downloads, legacy-implementation restoration, or R1 work.
