# Litmus R1 — local review candidate

Draft release. **Not security-cleared for a stable release.**
The package's historical 0.0.0 version remains unchanged; this is a Git milestone
snapshot, not a new PyPI distribution or a new scientific configuration.

Includes the local CLI/browser evidence workbench, image provenance inspection,
writing observations, frozen text calibration/evaluation, improved status recovery,
bounded uploads, accessible focus and honest result explanations.

Install: [INSTALL.md](../INSTALL.md). Architecture, screenshots and measured
results: [README.md](../README.md). Review: [release readiness](RELEASE-READINESS.md).
Portfolio/demo narrative: [PORTFOLIO.md](PORTFOLIO.md).

Validation: 883 default tests inside/outside; Ruff, dependency consistency,
installed-wheel, browser workflows and frozen scientific verification passed in
the retained readiness evidence. Four additional production browser journey checks
passed during release preparation. No held-out rescoring or recalibration.

Known limitations: advisory matches in filelock/pip/torch/transformers remain
unresolved; frozen environment was not upgraded. Full screen-reader and alternate
hardware checks are untested. Local single-user only. Historical transfer-cap
compliance remains unproven and legacy G interruption recovery is retired. No
models or RAID raw texts are included. MIT covers original project materials;
third-party materials retain their own licenses. Original evidence is preserved.
