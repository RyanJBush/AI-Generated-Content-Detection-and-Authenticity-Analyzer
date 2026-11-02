Done reviewing; here are the findings.

## Verdict
**Ready for private push.** I found no blocking defects. Two things to do before pushing, neither of which needs a code change: re-run the audit so it covers the publication commit itself (item 5), and fix one number in the doc (item 6).

## `src/litmus/local_ui/server.py` – the drain fix
1. **`server.py:152-172`: correct for the case you reproduced.** The JSON response is sent and flushed before any read, so the client already has its answer. `read1` serves already-buffered bytes first and then makes at most one raw read per loop. A timeout raises `socket.timeout`, which is an `OSError` and is caught. After that, reads on the timed-out socket fail, but the connection is closing anyway, so that's harmless. There are two hard limits (64 KB and a 50 ms absolute deadline), and the drained bytes are never parsed or framed. This also works on the `send_error` path for request-line and header parse errors, and when called after an upload read has already timed out (`server.py:291`): `read1` raises and gets caught.
2. **Limitation, not blocking: `server.py:160`.** The 64 KB cap means that rejections arriving with a large body can still be reset on Windows before the JSON arrives. That covers 413 on files over 50 MB (`:259`), 409 busy (`:285`), and real-file 415/400 rejections. A browser may then show a generic network error instead of the message. This was already true before the fix; consider adding one line about it to the limitations in `GITHUB-PUBLICATION.md`.
3. **Minor: `server.py:159`.** `HTTPServer` is single-threaded, so each error response can now delay the next request by up to 50 ms. The client's own response isn't delayed. That's acceptable for a single local user.

## `tests/test_local_ui.py`
4. **`test_local_ui.py:174-183`: the test is probabilistic.** At the reproduced 4% failure rate, the old code would still pass 100 iterations about 1.7% of the time (0.96¹⁰⁰). That's fine as a regression signal but it isn't deterministic. It also covers only the Transfer-Encoding case, not a body over 64 KB. That gap is consistent with item 2, so nothing to change.

## `scripts/audit_publication.py`
5. **Coverage gap: `audit_publication.py:73` and `history_audit.json:3`.** The audit recorded `head` = `1702de6`, so the commit you're about to push isn't scanned. That commit contains `server.py`, the scripts, `INSTALL.md`, `LICENSE` and `eval/results/publication/*`. Re-run the audit after committing and before pushing. If the re-run changes `history_audit.json`, that's a self-referential update and should be noted.
6. **Doc doesn't match the artifact: `GITHUB-PUBLICATION.md:16`.** The doc says "689 … blob objects, 35,023,132 bytes". `history_audit.json:9` has `"bytes": 35222780`, and that figure is the total across all object types (`audit_publication.py:48`), not just blobs. Update the number or the label.
7. **Minor pattern gap: `audit_publication.py:12`.** The private-key pattern misses `BEGIN ENCRYPTED PRIVATE KEY` and `BEGIN PGP PRIVATE KEY BLOCK`. The documented limitations (`:78`) already cover this kind of gap. The allowlist at `:59` requires both the object ID and the path to match, which is good and strict.
8. **Minor: `audit_publication.py:84`.** This script overwrites its output without asking, unlike `verify_ui_engines.py`. That's acceptable for a regenerable audit. `--all` also includes stash and remote-tracking refs, so it scans more than the two refs being pushed, which is the safe direction.

## `scripts/verify_ui_engines.py`
9. **No defects found.** The script validates before writing (`:136`), and opening with `"x"` (`:138`) still prevents an overwrite if the file appears between the `exists()` check and the write. Very minor: `read_text()` at `:16` and `:79` uses the locale encoding. That's harmless while the freeze and preflight JSON files are ASCII.

## Limitations of this review
- I only read the code. I didn't run anything, and I'm not claiming any test results.
- Item 2 is reasoned from the code, not reproduced.
- I didn't re-check the E/F/G scientific paths. Nothing in these five files touches them.
