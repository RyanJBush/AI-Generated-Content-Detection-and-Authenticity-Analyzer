# Professional-readiness verification — 2026-11-02

Scope: local single-user product, baseline 0afbb5a, branch
codex/recruiter-readiness. Codex performed executable checks. Claude performed
separate read-only reviews; their full text is retained alongside this record.
The implementation/evidence hashes in verification.json bind the tested files;
the containing Git commit supplies delivery identity. No circular commit hash.

## Release gates

| Gate | Classification | Actual result |
|---|---|---|
| Default tests, repository cwd | Verified Passed | 883 passed, 21 deselected, 29.41 s |
| Default tests, external cwd | Verified Passed | 883 passed, 21 deselected, 28.14 s |
| Ruff | Verified Passed | All checks passed |
| Dependency consistency | Verified Passed | No broken requirements found |
| JavaScript syntax | Verified Passed | node --check exits 0 |
| Fresh wheel | Verified Passed | wheel.json status PASS; all listed Litmus modules import from fresh installed wheel, pinned runtime dependencies reused without downloads |
| Browser journeys | Verified Passed | 17 checks in browser.json; actual keyboard, 390px layout, CSS 200% reflow, safe text rendering, export equality, failure/retry/reload |
| Recovery/native browser | Verified Passed | 6 checks in recovery.json; timeout timer accelerated to 100 ms in harness, not production; dismiss/retry and production constructed C2PA |
| Real-engine HTTP | Verified Passed | Two identical synthetic CUDA reports match frozen preflight; constructed C2PA uses production unknown-trust policy; saved JSON round-trip passes |
| Scientific identity/reassembly | Verified Passed | Accepted E/F reconciliation, original G identities, 17 artifacts, strict journal and saved metrics pass; 3361 rows/675 groups |
| Scoped accessibility | Verified Passed | Keyboard focus/skip link, mobile/desktop inspection, selected contrast pairs 5.49:1 or better, CSS zoom reflow |
| Static type checker | Not Applicable | No configured type-checking gate; no type-safety certification |
| Full slow suite | Not Tested | 21 slow tests excluded; narrow synthetic CUDA check does not substitute for entire suite |
| Full accessibility/other browsers | Not Tested | No screen-reader audit or exhaustive WCAG assessment; CSS zoom is not every browser zoom mode |
| Dependency vulnerability/advisory audit | Not Tested | pip check establishes consistency, not absence of CVEs |
| Alternate machine/GPU/fresh dependency acquisition | Not Tested | Existing pinned local runtime only |
| Public hosted deployment | Not Applicable | Local-only scope; no proxy/multi-user production claim |

No failing final applicable gate observed. History credential-pattern scan is
run against the final commit and recorded separately outside Git to avoid a
receipt cycle. Its limitations and permitted constructed test keys still apply;
this is not a guarantee that every possible secret format is absent.

## Exact commands and inputs

From C:/Users/Ryano/Projects/litmus:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pip check
node --check src/litmus/local_ui/static/app.js
.venv\Scripts\python.exe scripts/verify_wheel_r1.py --output eval/results/readiness/wheel.json
.venv\Scripts\python.exe scripts/verify_ui_engines.py --output eval/results/readiness/ui_engine_reports.json
.venv\Scripts\python.exe scripts/verify_ui_engines.py --verify-saved --output eval/results/readiness/ui_engine_reports.json
.venv\Scripts\python.exe scripts/verify_r1_release.py --metrics
git diff --check
```

Outside run cwd: C:/Users/Ryano/AppData/Local/Temp:

```powershell
C:\Users\Ryano\Projects\litmus\.venv\Scripts\python.exe -m pytest C:\Users\Ryano\Projects\litmus\tests -q
```

The wheel and real-engine writers refuse existing outputs; preserve receipts
and choose a new output path to repeat. The --verify-saved engine command
checks saved reports without executing CUDA again. The scientific verifier
opens saved metadata/scores/draws only, never held-out text.

Browser harness reproduction: start the constructed helper with
`.venv\Scripts\python.exe scripts/smoke_local_ui.py` (8766), and production
with `.venv\Scripts\python.exe -m litmus.local_ui --port 8768`. Execute the
async functions in scripts/browser_readiness_checks.js and
scripts/browser_recovery_checks.js using the existing Playwright tool. These
are local tool harnesses, not npm/CI tests; adapt the explicit workspace paths
for another machine. Use separate fresh browser contexts: recovery intentionally
accelerates the client's 30-second timeout to 100 ms while injecting a 500 ms
response delay. The main final 17-case run used an unmodified timer/context.
No Playwright package was added to Litmus. Screenshots depict production 8768,
constructed text, quality on, origin off; no detector result is implied.

## Boundaries and limitations

All frozen source maps, calibration, ledgers, lexicons and historical scientific
receipts remain intact. No held-out text was opened or rescored, no threshold
or formula changed, and no dependencies were added. Historical transfer-cap
compliance remains unproven; the accepted exception is unchanged. Historical G
recovery remains an unmet/retired requirement, not retroactively repaired.

A timeout or dismissed status never cancels native work. Lost POST replies can
leave a running job without a known ID. Hard termination/cleanup errors can
leave temporary files. Slow request headers can occupy the single local server;
body deadlines do not establish hardened public hosting. Native network
isolation and arbitrary hostile input safety are not comprehensively proven.
Local paths/author identity remain visible in private evidence. Review privacy
again before making the repository public. No fabricated adoption, author
provenance, third independent implementation session or universal ML accuracy.
