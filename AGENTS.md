# Agents Guidance

## Builder (Claude Code)
- Primary implementation of Blocks 1–3, 5 and 6.
- Uses commits as checkpoints.
- Must verify every numerical result.

## Block 4 builder (Codex, separate git worktree)
- RAID sampling, calibration, leakage controls, and evaluation (Block 4). Approved by Ryan 2026-10-26.
- Shared interfaces are listed in `docs/interfaces.md`; changes are coordinated through Ryan.

## Reviewer (ChatGPT / Codex)
- Reviews blocks against `SPEC.md` at checkpoints A, B, C and final.
- Audits for leakage and mathematical correctness.
