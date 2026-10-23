# Agents Guidance

## Builder (Claude Code)
- Primary implementation of all blocks (1–6).
- Uses commits as checkpoints.
- Must verify every numerical result.

## Reviewer (ChatGPT / Codex)
- Reviews blocks against `SPEC.md` at checkpoints A, B, C and final.
- Audits for leakage and mathematical correctness.
