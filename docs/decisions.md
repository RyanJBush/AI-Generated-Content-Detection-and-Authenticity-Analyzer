# Decisions

| Date | Decision | Rationale |
| :--- | :--- | :--- |
| unknown | Model: gemma4:31b-cloud, Backend: Ollama (cloud) | Required for current session runtime; verified via session startup. |
| unknown | SPEC derived from SPEC-v0_3_1.md (SHA-256 6829a54da03ecde1b535afda9fbb771f491cb6abe326a8b84435689c9a08a7ac) | Modified roles for Claude Code to build Block 4; current SPEC hash differs from source. |
| unknown | Correction | a9a83dc recorded a v0.3.2 update before the file existed; corrected. |
| unknown | Venv created with Python 3.13.7, PyTorch 2.6.0+cu124 | CUDA 12.4 verified on RTX 4060. Global install (bpag1fv08) ignored. |
| unknown | SPEC v0.3.2 COMMITTED | Hash 4b04892d65585d4c8d8ba9f07bd6fda3225ac1c8e76350d0dce217d8d6816aec; commit e572000. |
| 2026-10-26 | Task 1 scripts committed after their outputs; outputs marked invalid/superseded | Outputs in 10d6103 predate the source commit and do not establish checkpoint A. See docs/results-status.md. Checkpoint A not passed; D11/D12 Open. |
| 2026-10-26 | Candidate Qwen2.5 revisions pinned in `src/litmus/config.py` (`MODEL_REVISIONS`); selected pair not chosen | Tokenizer checks require commit SHAs, not `main`. SHAs are what `main` resolved to in the local HF cache. Pair/dtype selection awaits Task 1 review; D11/D12 Open. |
| 2026-10-26 | Simulated benchmark/drift retired; 0.5B fp32 benchmark run through the production scorer | `eval/benchmark.py` calls `litmus.binoculars`; old outputs kept with SUPERSEDED.md in `eval/results/superseded/`. First fp32 run superseded (host-memory and reserved-memory measurement defects). 1.5B, deployment, drift: not run. Checkpoint A not passed; D11/D12 Open. |
