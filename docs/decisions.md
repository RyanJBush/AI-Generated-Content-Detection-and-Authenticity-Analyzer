# Decisions

| Date | Decision | Rationale |
| :--- | :--- | :--- |
| unknown | Model: gemma4:31b-cloud, Backend: Ollama (cloud) | Required for current session runtime; verified via session startup. |
| unknown | SPEC derived from SPEC-v0_3_1.md (SHA-256 6829a54da03ecde1b535afda9fbb771f491cb6abe326a8b84435689c9a08a7ac) | Modified roles for Claude Code to build Block 4; current SPEC hash differs from source. |
| unknown | Correction | a9a83dc recorded a v0.3.2 update before the file existed; corrected. |
| unknown | Venv created with Python 3.13.7, PyTorch 2.6.0+cu124 | CUDA 12.4 verified on RTX 4060. Global install (bpag1fv08) ignored. |
| unknown | SPEC v0.3.2 COMMITTED | Hash 4b04892d65585d4c8d8ba9f07bd6fda3225ac1c8e76350d0dce217d8d6816aec; commit e572000. |
