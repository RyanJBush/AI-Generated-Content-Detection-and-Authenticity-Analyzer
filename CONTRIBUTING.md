# Contributing to Litmus

Start with [README.md](README.md), [installation](INSTALL.md) and the
[release-readiness assessment](docs/RELEASE-READINESS.md). Current remaining work
is tracked in the [R1 milestone](https://github.com/RyanJBush/litmus/milestone/1).

Open a focused issue before a substantial feature or dependency change. Use a
branch and pull request; describe the user-visible problem, change and actual
verification. Do not imply that unrun checks passed. Changes to the local UI
should retain the shared report assembler and original JSON evidence.

## Scientific boundaries

Frozen E/F/G source maps, original calibration, manifests, ledgers and receipts
are historical evidence. Do not rewrite them, reuse thresholds under a changed
configuration, score held-out texts again or silently alter dataset selection.
A dependency/model/formula migration requires its own reviewed plan. Preserve
the transfer-accounting exception and retired legacy recovery limitation.

Never commit datasets, model weights, personal documents, credentials or private
reports. Use constructed fixtures for regression tests. Existing test signing
keys are intentionally synthetic; never use them for real signatures.

## Verification

With the existing development environment, from the repository root:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pip check
git diff --check
```

Run relevant additional checks when the change warrants them; exact browser,
wheel and read-only scientific checks are documented in
[readiness evidence](eval/results/readiness/VERIFICATION.md). Default tests omit
the slow marker. They are not a full model, accessibility or vulnerability audit.
No GitHub Actions pass or hosted CI gate is claimed; current checks are local.
Do not enable paid runners, download models or run scientific evaluation merely
to satisfy a pull-request checklist.

Report security concerns through [SECURITY.md](SECURITY.md). AI-assisted changes
are welcome when their role and actual verification are disclosed accurately.
