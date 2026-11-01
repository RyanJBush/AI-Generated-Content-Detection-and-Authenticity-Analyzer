# R1-E acquisition approval request

**APPROVED by Ryan on 2026-10-31**, together with E0–E6 in the complete
[R1-E plan](R1-E-PLAN.md). The request below is retained as the approved scope.
Ryan also reported reviewer confirmation of the revision-specific API byte/hash
metadata; the builder must independently repeat preflight before transfer.
No scoring, calibration, test evaluation, UI or new dependencies are authorized.

**Narrow historical exception:** Ryan subsequently accepted the uncertainty in
`r1e_redirect_budget_audit.json`, not proof of original transfer-cap compliance.
He authorized an offline correction and source-version reconciliation, retaining
the existing data/outputs with no reacquisition or further network requests.
R1-E remains pending independent review. The execution update below describes
the original b2d24da stop, not the corrected downloader; the original counters
and receipts remain unchanged. See `r1e_budget_fix_verification.json` for follow-up.

**Execution update (2026-10-31):** the builder repeated revision-specific API
preflight immediately before transfer, then verified all 11,779,491,051 local
bytes against the approved SHA-256. See `eval/manifests/r1e/preflight.json` and
`acquisition.json`. Counted API/artifact payload was 11,779,495,917 bytes;
conservative charged usage for those reads was 11,781,588,203 bytes. **STOP:
redirect bodies were read by urllib outside those counters. Their actual byte
count was not captured, so the full 13 GB cumulative cap is not proven. No actual
overrun is established.** See `eval/results/r1e_redirect_budget_audit.json`.
No reacquisition or source patch followed this finding; independent review is
required. Free disk before acquisition was 426,871,160,832 bytes. The planning
wording below is preserved historically; acquisition is now approved and done.
No alternate artifact, fallback route or paid service was used.

## Existing authorization and requested decisions

N_target = **1,000 source groups** was approved on 2026-10-30. D3/R1-D closure
is based on Ryan's supplied independent review of d7ed91f: 660 default tests,
Ruff, pip check, whitespace and fresh installed-wheel verification passed.
Neither approval authorizes RAID acquisition, scoring or calibration.

Request explicit approval for the following bounded acquisition:

| Item | Requested scope |
|---|---|
| Publisher/repository | authors' liamdugan/raid dataset on Hugging Face |
| Revision | 865cac74188466cb0c3b7574a10204007b57a459 |
| Artifact | train.csv only; no test.csv, extra.csv, train_none.csv or repository clone |
| Expected size | 11,779,491,051 bytes (about 11.779 GB / 10.97 GiB) |
| Advertised SHA-256 | 52f04ceebc126064e68fbd22d8b736964065745464f4bfd52e488150b49f84e4 |
| License declaration | dataset card MIT; local evaluation only, attribution retained; no raw-text redistribution |
| Transfer ceiling | 13,000,000,000 cumulative payload bytes including retries; no paid service |
| Disk gate/ceiling | recheck ≥30 GB free; ≤25 GB incremental task artifacts including preserved partials/indexes/outputs |
| Dependency changes | none; existing venv, standard-library CSV/HTTP/SQLite and existing pinned tokenizer dependencies |

Proposed pinned payload URL, **not fetched**:

`https://huggingface.co/datasets/liamdugan/raid/resolve/865cac74188466cb0c3b7574a10204007b57a459/train.csv`

Before transfer, confirm the exact revision-specific pointer/API metadata agrees
with the advertised length/hash, then verify downloaded bytes locally. The
[revision tree](https://huggingface.co/datasets/liamdugan/raid/tree/865cac74188466cb0c3b7574a10204007b57a459)
was verified, but its exact blob/pointer could not be retrieved by the browser.
The byte count/hash above are published in the immutable
[file-addition commit](https://huggingface.co/datasets/liamdugan/raid/commit/6749693cab9ccb7452a32d575ecb80abff57b2c0)
and advertised on the [current file page](https://huggingface.co/datasets/liamdugan/raid/blob/main/train.csv).
Mismatch or inaccessible identity stops the run; this request is not approval
to substitute a mutable revision, another host or a larger artifact.

The [official GitHub download instructions](https://github.com/liamdugan/raid#download-raid)
also publish dataset.raid-bench.xyz/train.csv. This mutable route is documented,
not an approved fallback. The [official dataset card](https://huggingface.co/datasets/liamdugan/raid/blob/main/README.md)
declares MIT. Underlying source-corpus redistribution terms have not been fully
audited; this request does not choose Litmus's project license.

## Expected costs and limitations

Expect one full 11.779 GB transfer even for a 1,000-group sample. Streaming
avoids loading the corpus in memory; it does not avoid downloading/scanning
unselected text. Do not buy bandwidth/storage or use a paid API. Provider fees
are not expected; ISP charges and actual throughput are unknown. Ideal transfer
lower bounds at 50/100/500 Mbit/s are about 31.4/15.7/3.1 minutes, before overhead.

Raw storage is about 11.779 GB. The plan estimates roughly 13–20 GB total with
metadata indexes, selected text blobs and audit outputs, within the 25 GB ceiling.
Actual row counts/index sizes are unknown. The planning check found about
419.24 GB free on C:, which must be rechecked, not assumed at execution time.

No publisher test/extra split, Parquet mirror or Hub whole-dataset cache is
needed. Only RAID-train supplies the proposed grouped Litmus dev/test subsets.
Actual schemas, label/null conventions, quotas, attack availability and retained
counts remain unverified until an approved full-file scan. No guaranteed
1,000 retained groups, 300 dev groups or 200 eligible dev human texts is claimed.

## Implementation approval is separate and explicit

If approving the plan as well as acquisition, approve the proposed seed
20261030 and E0–E6 in R1-E-PLAN.md, including:

- CA1 pure key/tests first, before acquisition/selection; absent at present;
- metadata-only source-unique per-cell quotas with no reallocation/refill;
- independent select/split/row tags and grouped 30% hash assignment;
- metadata-only attack multiplicity tie-break with the row tag;
- tokenizer-only eligibility, raw/window deduplication and single-pass cleanup;
- reproducible manifests/counts/exclusions, followed by commit and independent review.

Suggested combined approval wording for Ryan to edit or decline:

> Approve R1-E-PLAN.md and the bounded acquisition described here, conditional
> on the pinned metadata/byte/hash match, stated budgets and CA1 prerequisite.
> Authorize E0–E6 data preparation only. No scoring, calibration or test evaluation.

Approval of acquisition alone does not authorize implementation unless Ryan
explicitly approves the preparation plan too. Saving, reviewing or recommending
this request does not grant either permission.

R1-E produces no detector scores. Future 5% calibration requires at least
**200 eligible development human texts after every exclusion and pair cleanup**;
the 1% calibration stays disabled. Falling below 200 is reported, not repaired
by a seed search, test-to-dev move or unapproved target increase. R1-F calibration
and R1-G test scoring remain separate gates. No UI or additional scope is requested.
