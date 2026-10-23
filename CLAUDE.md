# Project-specific instructions for Claude Code

## Core Principles
- **Spec First:** Read `SPEC.md` before every block.
- **No Fabrications:** Never report a metric or result not produced by actual code execution in this repo.
- **Leakage Control:** Strictly follow §7.2 for splits and freeze.
- **Honest Reporting:** Document all deviations, skipped runs, and limitations.

## Technical Constraints
- Max input length: 512 tokens.
- Float32 reductions for all Binoculars statistics.
- No chat templates or special token appending for Layer A.
- Original character offsets for Layer B.

## Handoff Format
Each review checkpoint requires:
1. Task ID, branch/commit, changed files.
2. Implementation summary + spec deviations.
3. Exact commands and result paths.
4. Elapsed time and hardware/runtime stats.
5. Proposed next task.
