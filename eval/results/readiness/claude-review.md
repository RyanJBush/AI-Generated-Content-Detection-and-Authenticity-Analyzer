# Litmus recruiter-readiness review: `codex/recruiter-readiness` (baseline `0afbb5a`)

I found no P0 or P1 defects. There are three P2 items worth fixing before you show this, plus several P3s. The science wording is careful and is the project's strongest point. The main recruiter-facing weakness is still how the README opens. I'd be comfortable showing this as a private portfolio piece once the README rewrite lands and ideally the first two findings are fixed. I agree public hosting is out of scope (reasons at the end).

**What I read:** `docs/plans/RECRUITER-READINESS.md`, `README.md`, the UI-related parts of `SPEC.md`, the local-UI section of `docs/interfaces.md`, the OpenAPI response section, `local_ui/server.py`, `analysis.py`, all static files, `tests/test_ui_readiness.py`, `tests/test_local_ui.py`, `report.py`, `offline.py`, `scorer/analyzer.py`, `scorer/calibration.py`, and the reason strings in `ingestion.py` and `quality/observers.py`.

**What I didn't do:** I ran nothing (no tests, no git commands, no diffs) and opened no network, model or raw-dataset files. I didn't open INSTALL.md, `R1-PLAN-CORRECTIONS-A.md` (searched it, but found nothing UI-related) or the screenshots. Because I couldn't diff, "frozen E/F/G paths untouched" rests on the git status snapshot, which shows only UI files, the plan and the new test as changed. That's consistent with no frozen edits but isn't proof.

## Findings

### F1 · P2 · Confirmed: there is no way out of a "pending" analysis except restarting the server or opening a new tab
- **Where:** `app.js:30-31` (`controls` locks the file input and switches whenever `pending !== null`), `app.js:36` (`selectFile` returns early when pending), `app.js:114` (pending is cleared only on 403/404).
- **Evidence:** If status checks keep failing with a 500, an unreadable response, a network error or an unknown job state, the retry button is the only control left. Reloading restores the same pending ID from tab storage and fails again.
- **Fix (small):** Add a secondary "Forget this analysis" button that clears `pending` and tab storage, with copy saying it doesn't cancel local work. A later upload may then get a 409 until that work finishes.
- **Acceptance:** In a browser fault test with the status endpoint stuck on 500, the user can clear the state and select a new file. No POST is sent until they click Analyze.

### F2 · P2 · Confirmed: server and job failures leave no diagnostics anywhere
- **Where:** `server.py:83-89` (the job exception is swallowed), `server.py:126-129` (the new 500 path), `server.py:131-132` (`log_message` does nothing). There are no logging calls in the file.
- **Evidence:** A user who sees "Analysis could not finish. Check the file and local model setup." can't tell a CUDA failure from a bad file or a temp-cleanup failure. An engineer evaluating the project will notice this.
- **Fix (small):** Print the exception type and traceback to the server's own console (never the browser), via `traceback.print_exc()` or `logging.exception`. Optionally put it behind `--debug` to keep console noise down.
- **Acceptance:** The injected-exception test still returns the generic JSON 500 without the private text, and stderr (captured with `capsys`) contains the exception type.

### F3 · P2 · Confirmed: content-observation limitations are tucked away where they read as legacy text
- **Where:** `app.js:79-90`, `report.py:29-40`.
- **Evidence:** The quality card shows only the generic "do not establish AI origin" line. The scientifically important caveats only appear in a collapsed section titled "Original report limitations", next to the frozen "R0 skeleton" wording, which makes them look obsolete. Those caveats are:
  - English-only lexicons
  - CJK word-count distortion
  - homoglyph and zero-width evasion
  - the 1,000-span cap
- **Fix (small):** When quality observations ran, list `value.limitations` inside the quality card, or keep them in place but rename the section to something like "All recorded report limitations (verbatim)". I didn't see the baseline, so I can't say whether this is a regression.
- **Acceptance:** A text report with Content observations on shows the English/CJK/homoglyph caveats without expanding anything. The exported JSON is byte-identical to before.

### F4 · P3 · Confirmed: several plain-language reason mappings are dead or missing
- **Where:** `app.js:16` maps `model_not_installed`, but nothing produces that string. `analyzer.py:203-204` returns the exception message as the reason instead.
- **More dead code:** Loading is lazy (`analysis.py:20`, `analyzer.py:188-193`), so the `ModelNotInstalled` branch at `server.py:86` can't be reached through the text path.
- **Unmapped reasons** that fall through to "underscores become spaces" in `app.js:59`:
  - `too_short`
  - `no calibration for this configuration`
  - `execution_profile_incomplete` / `execution_profile_changed`
  - `numerical_error: …`
  - ingestion reasons such as `documents arrive in R2`
- **Fix:** Remove the dead key, or match on prefixes. Add short plain-language text for the reasons above, and keep the raw records as they are.
- **Acceptance:** A unit or browser check that renders each known reason shows non-raw text.

### F5 · P3 · Confirmed: a lost POST response leaves an analysis the user can't recover
- **Where:** `app.js:94`, `app.js:101`, `app.js:115`, `app.js:122-123`.
- **Evidence:** If the 30-second abort fires after the server accepted the job, `pending` is never set. The message then contradicts itself: "This does not cancel analysis" is followed by "Select your file or try again". Retrying gets a 409, and there's no endpoint for finding the current job.
- **Fix (no API change):** For a POST timeout, say "Litmus may have started this analysis; wait, then try again". For a 409, say "Another analysis is running (possibly from an earlier attempt)".
- **Acceptance:** Copy review, plus one fault-injection case.

### F6 · P3 · Risk: slow request headers can still hold the single-threaded server
- **Where:** `server.py:105` (one `HTTPServer` thread), `server.py:118` (`timeout = 10` applies to each socket read).
- **Evidence:** The new deadline covers only the request body. Headers that trickle in one byte every 9 seconds keep the server, including status checks, occupied indefinitely. A browser page can't do this, so the realistic threat is another local process, which is out of scope for a loopback tool.
- **Fix:** Document it as residual, or give header parsing an overall deadline.
- **Acceptance:** A residual-risk line in the docs, or a test that trickles headers.

### F7 · P3 · Risk: a fixed 10-second upload deadline for up to 50 MB
- **Where:** `server.py:22`, `server.py:307`.
- **Evidence:** That's fine over loopback. It could falsely reject when the browser reads slowly, for example from OneDrive files that are only stored online, a network drive, or under antivirus scanning.
- **Fix:** Use something like `10 s + length / (2 MB/s)`, with a cap, or add a hint to the upload error message.
- **Acceptance:** The trickle test still passes. A 50 MB upload throttled to 3 MB/s is accepted.

### F8 · P3 · Confirmed: the OpenAPI filename description has drifted from the code
- **Where:** `local-ui.openapi.json:37` says "no … control character". The code now also rejects Unicode format characters (`server.py:292-295`).
- **Fix:** Update the description only; the schema doesn't need to change.
- **Optional:** Also reject the line and paragraph separators U+2028/U+2029 and whitespace-only names. Both are currently accepted.

### F9 · P3 · Confirmed: the UI privacy line is more absolute than the README
- **Where:** `index.html:9` says "Temporary uploads are removed after analysis." `README.md:35-36` adds that a hard termination can leave a file, and the plan records that cleanup can fail.
- **Fix:** Add "…normally removed after analysis; a forced stop can leave one in your temp folder."

### F10 · P3 · Calculated: the focus ring is below 3:1 on the page background
- **Where:** `style.css:2`.
- **Evidence:** By my own sRGB calculation, the focus colour `#609ba4` is about 3.1:1 on white but about 2.86:1 on the page background `#f5f5f0`. That affects the wordmark link and the skip link's outer ring.
- **Fix:** Use a darker ring (the accent `#135d68` is about 7:1) or a two-tone outline.
- **Acceptance:** Recorded contrast calculations show at least 3:1 on every background where focus can appear.

### F11 · P3 · Risk: keyboard focus is lost when Analyze is clicked
- **Where:** `app.js:118` disables the button that currently has focus, so focus can drop to `<body>`.
- **Fix:** Move focus to `#status`, or use `aria-disabled` instead of `disabled` while the analysis runs.

### F12 · P3 · Confirmed: the trickle test's assertion is weak
- **Where:** `test_ui_readiness.py:95`.
- **Evidence:** `b"400" in data` would also match a header value.
- **Fix:** Parse the status line and assert `error.code == "upload"`.

### F13 · P3 · Confirmed: a render failure can repeat on every reload
- **Where:** `app.js:109-111`.
- **Evidence:** If `render` throws, `pending` has already been cleared but tab storage still holds the job, so every reload re-renders the same report and throws again.
- **Fix:** Save the job only after a successful render, or clear storage in the catch.

## Matches the stated changes, by reading

These are code-reading checks only; none of this was tested by me.
- **Recovery:** Page load calls only `recover()`, which sends a GET; it never POSTs (`app.js:137`, `app.js:126-129`). Tab storage holds only `{id, options}`; no token, file or text is stored (`app.js:111`, `app.js:123`).
- **500 handling:** It is guarded by `_response_started`, so a response can't be sent twice.
- **Upload deadline:** It's an absolute deadline with reads of at most 64 KiB. The busy check happens before the body is read.
- **Filenames:** Cc/Cf characters are rejected. The client filename never becomes a path on disk (`server.py:72-75`).
- **Disabled checks:** "Not run" depends on the `_placeholder` method IDs (`report.py:57`, `report.py:68`). With text-origin on, the real `binoculars` ID is used, so a check that ran isn't mislabelled.
- **Rendering and CSP:** Reports render with `textContent`, and the CSP allows no inline script.
- **Science copy:** The UI wording on 512 tokens, scores not being probabilities, the empty trust list and the homoglyph weakness matches the code and the README's G table.
- **Test count:** The two files contain 39 test cases (counting parametrized cases), which matches the "39 focused" figure. I didn't run them.

## Missing evidence

- No automated JS or browser tests exist for the Not-run display, recovery, retry, timeout or the 200% reflow. The plan's browser fault-injection acceptance criteria rely on manual or agent-run evidence, and there's no `eval/results/` folder for this branch yet.
- I couldn't verify the full suite result, the Ruff run, the wheel check, the frozen-science verifier or byte-identical exported JSON.

## Documentation suggestions

- Open the README with three lines: what it does, how it works locally, and an honest headline result. For example: "AUROC 0.80; at the frozen 5% development threshold, 66% TPR / 4.6% FPR on a held-out RAID subset; fails badly under homoglyph edits". Then a screenshot and a short architecture diagram (browser → loopback server → one worker → `run_analysis` → frozen scorer/calibration). Move the E/G provenance status out of the opening block into a "Scientific provenance" section. As it stands, recruiters hit "transfer-cap compliance remains unproven" before they learn what the tool does.
- Add one sentence explaining that the exported JSON keeps the frozen `litmus-report/r0` schema and its historical limitation strings ("R0 skeleton…", "there is no C2PA analysis"). That way a reader opening the download isn't confused (`report.py:20-27`).
- Update the "632 passed" figure once the full run on this branch finishes, rather than carrying over the R1-H number.

## Readiness

**Private portfolio:** Yes. The hedged, interval-reported evaluation, the frozen calibration with hash binding, the honest "not a probability" UI and the documented residual risks show unusually mature judgement. Fixing F1–F3 and finishing the README rewrite would remove the most visible rough edges. The P3s can be listed as known limitations.

**Public hosting:** Out of scope. Several properties are fine for one person on one machine but unsuitable for a public service:
- one server thread and one GPU worker
- the access token is embedded in the page
- the offline guards patch the whole process
- the last report stays in memory
- there's no authentication or rate limiting

Hosting it would need a redesign, not hardening. Before changing the repo's GitHub visibility, do the privacy review the plan already calls for.
