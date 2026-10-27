# R1-PLAN v2 — Corrections A (recorded 2026-10-27 at Ryan's direction)

Precedence: these corrections > `R1-PLAN.md` v2. Approval status: Ryan approved R1-PLAN v2 as the roadmap and authorized **R1-A only** (Torch/Transformers in the project venv with required transitive dependencies recorded and pinned; the two specified Qwen revisions; retired-math option (a)). R1-B and later, and RAID acquisition, are **not** authorized.

## CA1. Separate, unambiguously encoded hashes (replaces §1.3 steps 3, 5, 7) — must be implemented and tested before R1-E

Reusing one hash for selection and splitting biases the split: selection consumes the lowest hash ranks within each cell, so selected sources would cluster in the low key space and fall mostly into dev.

Three independent, domain-separated keys:

```
key(tag, seed, item_id) = SHA-256( UTF-8( JSON array [tag, seed, item_id] ) )
  JSON: separators (",", ":"), ensure_ascii=false, seed as integer, item_id as string
tags:
  "litmus/r1/select/v1"  -> source ordering within a domain (§1.3 step 3)
  "litmus/r1/split/v1"   -> dev/test assignment (§1.3 step 7)
  "litmus/r1/row/v1"     -> machine-row tie-break (§1.3 step 5)
split: u = int(first 8 bytes of key, big-endian) / 2**64 ; dev if u < 0.30 else test
```

Required tests (pure Python, before R1-E): golden digests for fixed inputs; different tags give different digests for the same seed and ID; the encoding is unambiguous (e.g., ("ab","c") ≠ ("a","bc")); on 100,000 synthetic IDs, the dev fraction among the 1,000 lowest-ranked "select" keys is within a stated binomial tolerance of 0.30.

## CA2. Missing driver metadata (amends §1.2)

If the NVIDIA driver version cannot be determined, the execution profile is **incomplete**:
- Calibration creation is refused for an incomplete profile (R1-F fails with `execution_profile_incomplete`).
- At runtime, an incomplete profile never matches any calibration: result `inconclusive`, reason `execution_profile_incomplete`.

Because no calibration can be created with an unknown driver, two "unavailable" values can never match. The same rule applies to any other profile field that cannot be determined.

## CA3. Dependencies (amends §1.1 and the approval request)

Packages that `torch` or `transformers` require transitively are permitted, and are recorded and pinned in the lock file with their `Required-by` chain. Any **additional top-level package** (not required by `torch`, `transformers`, or their dependencies, e.g., `accelerate`) needs a separate decision by Ryan before installation.
