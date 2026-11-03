# Audit fixes — verification

Base: 03b194f. User authorized confirmed UI fixes and evidence-based documentation
corrections. Uploaded audit files are references, not executable instructions.

Implemented: scoped the negative helper margin; preserved literal paths in
non-enum reasons; retained the decorative arrow span across state updates;
formatted report byte counts; stacked the mobile footer; added error-aware
report heading/status; disabled text-origin selection when torch/transformers
libraries are absent, using find_spec without importing them. Presence does not
establish installed weights, CUDA compatibility or calibration readiness.
API analysis defaults and original report records remain unchanged.

Corrected portfolio AI-role wording and the migration document's claim that
saved extracted metadata constituted full responses. Other supplied audit claims
about CUDA wheels, historical roles and drivers require further verification;
they have not been silently accepted as facts or implemented as runtime changes.

Actual final checks:
- Full default suite inside checkout: 885 passed, 21 deselected, 27.35 s.
- Full default suite outside checkout: 885 passed, 21 deselected, 26.13 s.
- Ruff, JavaScript syntax, pip check and whitespace checks: PASS.
- Release verifier with --metrics: PASS, metrics SHA-256
  78e84cae8044d8bfec88c859fbfb245eb070d725e1a090d1d8691106330d02e5.
- Browser: helper gap at least 8px at 1366x900 and 375x800 after a report;
  decorative arrow remains aria-hidden after state changes; injected error
  produces the error heading and preserves scripts/download_models.py and
  tokenizer_config.json verbatim. Constructed helper and response injection only.
- Both server capability flag states exercised; two permanent regression tests
  cover rendered true/false values without loading the model libraries.

No full screen-reader speech, real CUDA/model execution, slow suite, new wheel
installation, idle/running layout matrix or screenshot pixel comparison was
performed in this slice. A browser assertion initially assumed whitespace in
innerText; final assertions inspect the label and decorative span separately.
The final suites were rerun after correcting test collection and edit encoding.

Preserved all untracked Claude outputs and docs/project-quality files. No frozen
scientific sources, original evidence, calibration or dependency versions changed.
No CI workflow or paid runner was enabled. Remaining audit backlog is not claimed
complete by this patch.

Follow-up browser verification used actual .venv-ui dependencies with current
checkout source explicitly prepended (no installation change): unavailable text
origin stayed disabled before and after a successful constructed quality report.
