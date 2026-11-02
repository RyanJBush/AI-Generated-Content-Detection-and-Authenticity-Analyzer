# Issues 1–3: verified progress, 2026-11-02

Base: f4b480f, including Copilot triage PR #4. Ryan requested fixes and confirmed
no second computer is available. This follow-up does not close all three issues.

## 1. Dependency security

Live OSV refresh succeeded: 37 original environment packages, the same 59
advisory records. Copilot's 46-distinct-advisory triage remains the baseline.
The original snapshot and review's failed-refresh statement were preserved.
All 37 original installed versions were checked unchanged after this work.

Created an independent venv without system site packages, installed pip 26.2.2,
and installed a fresh Litmus wheel plus declared model-free dependencies. No
torch, transformers or filelock is installed there. Litmus imports from its
site-packages outside the checkout. Dependency consistency passed. A live OSV
query returned zero matches for its 12 third-party packages. Receipts retain
versions, package artifact URLs/hashes and OS/Python information.

INSTALL.md now uses a separate ignored .venv-ui. This improves the basic demo
setup without upgrading the frozen research environment. Zero returned matches
is not a security guarantee or a native binary/driver audit.

**Issue #1 remains open:** model-stack findings and the complete remediation
gate are unresolved. A changed scientific profile requires its own reviewed
migration; never reuse the existing threshold under a different configuration.

## 2. Accessibility

Reproduced a keyboard defect: activating Check analysis status disabled the
focused button and moved focus to BODY. Recovery now focuses the status message.
The message precedes the action buttons so Tab naturally reaches retry/dismiss.
An initial fix that retained the old message order failed the next-Tab test;
reordering resolved it. Reports and scoring are unchanged.

The final fresh-context Chromium run passed nine checks: skip link/order,
status focus after failed retry, polite live region, next Tab to retry, dismissal
focus, no-cancellation explanation, result heading focus and keyboard JSON export.
The browser version and accessibility tree are saved in accessibility.json.
Run scripts/browser_accessibility_checks.js through the existing Playwright tool
in a fresh context, with scripts/smoke_local_ui.py on 8766. Inputs and failures
are constructed. No browser dependency was added to the project.

Narrator 10.0.26100.8972 is installed. The computer-use launch_app attempt timed
out; subsequent window/process checks found no Narrator process. No speech was
observed. NVDA was not found at the standard installation paths checked.

**Issue #2 remains open:** actual screen-reader announcements are not verified.
The remaining manual check should record OS/browser/reader versions and actual
spoken labels for file selection, options, progress, results, export, errors,
retry and dismissal. Use constructed inputs. Narrator speech recap, where
supported, can retain utterances. See Microsoft's
[Narrator guide](https://support.microsoft.com/en-us/accessibility/windows/narrator/complete-guide-to-narrator)
and [speech recap instructions](https://support.microsoft.com/en-us/accessibility/windows/narrator/chapter-2-narrator-basics).
Keyboard/accessibility-tree success is not speech verification or WCAG certification.

## 3. Independent installation

The owner has no second computer. WSL lists only docker-desktop; the Docker Linux
engine was unavailable. No VM or second physical machine was tested.

A separate environment on this same Windows machine installed the wheel and
dependencies. Six production-browser checks passed: default options off,
content observations, text origin Not run, JSON identity, constructed C2PA
report and production signer_trust=unknown. Saved reports are constructed data.

**Issue #3 remains open:** this is stronger same-machine installation evidence,
not a second-machine result. On an available second machine or explicitly labelled
VM, follow INSTALL.md and record platform, commands, the two constructed fixtures
and JSON exports. Leave text origin off; no model setup is required for this check.

## Actual checks

- UI tests: 41 passed in 2.62 s (`python -m pytest tests/test_local_ui.py tests/test_ui_readiness.py -q`).
- `python -m ruff check .`, `node --check src/litmus/local_ui/static/app.js`: passed.
- Original and clean-environment `python -m pip check`: passed.
- Original 37 installed package versions: unchanged.
- Browser keyboard/recovery: 9 passed; clean installed UI: 6 passed.
- `python scripts/verify_r1_release.py --metrics`: PASS for original E/F/G identities,
  17 artifacts, strict journal and saved metrics. No test texts opened.
- Whitespace checks passed on the final changes.

Commands above use the original .venv unless marked clean. Clean environment:
C:/Users/Ryano/AppData/Local/Temp/litmus-clean-ui-20261102. The wheel was built
using the original interpreter's `pip wheel --no-index --no-deps
--no-build-isolation --no-cache-dir`, then installed with the clean interpreter
using `pip install --only-binary=:all: --report <receipt> <wheel>`.
Wheel SHA-256: b6ad95610aedec91ba09d0305c3094a19593913e502c1c84d4768655d21f1587.
Basic runtime packages came from pip's cache; pip 26.2.2 downloaded a 1.8 MB wheel.
No new project dependency, model weights or VM image was added.

No full/slow suite or CUDA checks were rerun for these UI focus and installation
changes. No scoring, calibration, threshold reuse or frozen-source edit occurred.
Historical transfer compliance remains unproven; legacy G recovery remains retired.
