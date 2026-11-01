# Current R1-E checkpoint

Current follow-up: Ryan accepted the specific historical uncertainty, never as
proof of cap compliance, and authorized an offline correction. R1-E pending review.
Follow-up baseline: b2d24daba14b80a0cc25c524045e7f713a0363b9, master.
Original execution checkpoint below is retained historically; no active old session.

- E0 verified before acquisition: nine CA1 tests; independent synthetic dev
  fraction 303/1,000 among the lowest select keys from 100,000 IDs.
- E1 accepted: API preflight and downloaded size/SHA-256 passed. Acquisition
  receipt is eval/manifests/r1e/acquisition.json. Confirmed received payload
  11,779,495,917 bytes, conservative charged usage 11,781,588,203 (<13 GB).
  Download session 18408 completed; do not download again.
- E2–E5 primary and repeat preparation produced outputs; raw-backed verification
  and seven-file repeat comparison passed. This does not close the budget gap.
  Latest synthetic slice: 40 passed. Final inside suite: 700 passed, 21 deselected
  in 14.95 s. Final outside suite: 700 passed, 21 deselected in 15.47 s.
  Explicit tokenizer-only slow check:
  one passed in 2.21 s, without weights/model imports/network. Ruff clean.
- Primary session 55179 completed normally. Full CSV: 5,615,820 unique IDs;
  13,371 eligible sources, 88 cells, no quota shortfall; 1,000 groups/5,000 rows
  selected, 973 groups/4,845 rows retained, 298 dev humans, 675 test groups.
  Primary guard attempts all zero. See r1e_primary_run.json and primary/counts.json.
- Repeat session 99947 completed exit 0: same 973 groups/4,845 rows/298 dev
  humans, same manifest SHA-256. Elapsed 634.764 s, CPU 521.656 s, peak working
  set 492,400,640 bytes; guards all zero. Do not overwrite either run.
- Raw-backed verifier session 64501 completed exit 0, PASS in 332.295 s:
  5,615,820 raw rows scanned, 5,000 selected texts recomputed, 4,845 retained
  blobs matched, all seven repeat scientific files byte-identical; guards zero.
  Raw+two runs+manifests = 14,213,226,786 bytes; with
  64 MiB reserve = 14,280,335,650 (<25 GB). Transfer journal unchanged.
- STOP: urllib's redirect handler calls fp.read outside Budget.read. Synthetic
  adapter audit consumed 23 bytes without changing counters, zero network.
  Actual redirect body length is unknown; total cumulative transfer compliance
  cannot be proven, although counted reads are below cap and no overrun is shown.
  Source, acquisition receipt and scientific outputs remain frozen. No fix or
  reacquisition is authorized by treating the stop as success. Preserve and commit
  work/evidence for independent review; no R1-F/R1-G work.
- Source code is frozen pending primary/repeat/verification. Changes to hashed
  sources after manifest generation require fresh identity-consistent outputs;
  do not silently patch over a real stop condition.
- Scripts: acquire_raid.py; prepare_raid.py --run-id primary/repeat;
  verify_raid_manifest.py --run-id primary --compare-repeat.
- Run preparation scripts in fresh existing-venv processes under their guards.
  Do not run the whole slow suite, scorer or any evaluation.
- Preserve partial files, source/docs and evidence. Existing completed run
  directories must not be overwritten. Stop for real schema/identity/budget failure.

Resume order: user approval -> parent plan/request -> this checkpoint -> git
status/HEAD -> transfer journal and running-session status -> code/evidence.
Next: finish documentation/evidence and scoped Git checks; commit preserved work
with explicit budget STOP, read back commit/status, then stop for independent review.

## Follow-up checkpoint

- Corrected redirect/default HTTP error handlers drain via shared Budget and close
  before following/raising; all aliases exercised offline. No HTTP/network requests.
- Source reconciliation is explicit and exact; three changed hashed paths only.
  Original maps/manifests/receipts remain unchanged. New verification outputs only.
- Source frozen after Ruff fix. RAID tests inside: 68 passed/1 deselected in6.62s;
  outside permitted rerun: 68 passed/1 deselected in5.72s. Initial outside sandbox
  run had temp-dir permission errors, not application failures. Ruff/pip check pass.
- Read-only existing-data/source preservation audit session4700 completed PASS:
  approved raw size/hash; 4,845 retained blob hashes per run; all seven scientific
  files identical; 26 original tracked evidence files byte-unchanged; exact
  source reconciliation passes and default mismatch rejects; guard attempts zero.
  No real selection/tokenization rerun. No active execution sessions remain.
- Final step: stage only follow-up paths, verify original evidence/staged source
  hashes, commit and stop for independent review. No R1-F/R1-G, network or acquisition.
