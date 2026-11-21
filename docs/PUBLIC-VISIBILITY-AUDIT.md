# Public visibility audit — 2026-11-21

Ryan authorized a pre-publication security audit and, if it passed, changing
`RyanJBush/litmus` from private to public. This record states what was checked
and what was not. It does not change code, frozen evidence or scientific results.

## Scope

- All reachable Git objects in a mirror clone: 7 branches, 2 tags and 5
  pull-request refs; 90 commits; every one of 790 reachable blobs; 513 distinct
  paths ever committed, including 75 no longer on `master`.
- Current `master` files, dependencies, launch scripts, the local server,
  model loading, screenshots and image fixtures.
- Open issues #1–#3 and repository metadata.

No third-party secret-scanning service was used and no source was uploaded
elsewhere. A local Python pattern scan covered private-key PEM headers;
GitHub, OpenAI, Anthropic, AWS, Google, Slack, Hugging Face, GitLab and Stripe
token formats; JWTs; bearer headers; credential-bearing URLs; quoted
password/secret/API-key assignments; email addresses; home-directory paths;
non-local IPv4 addresses; and phone-number patterns. A pattern scan cannot
prove that secrets in unknown formats are absent.

## Findings

| Area | Result | Disposition |
|---|---|---|
| Credentials and tokens | No matches in any blob | Pass |
| Private keys | Only `tests/fixtures/c2pa/pki/test_signer_key.pem` and `untrusted_signer_key.pem` | Generated test-only keys, documented in that folder's README; they protect nothing. Accepted. GitHub secret scanning may flag them. |
| `.env`, dataset text, weights | No `.env`, `data/raid`, `models/`, `train.csv` or `*.safetensors` path in history; the only historical `data/` files are three early project lexicons | Pass |
| Evaluation artifacts | IDs, labels, hashes, scores and metrics only; no RAID raw text | Pass |
| Author email | 89 commits carry `ryan.j.bush0@gmail.com` | Already public in commit metadata of `RyanJBush/relay` and `RyanJBush/project-14-earthquake-explorer`. Not a new disclosure; history not rewritten. |
| Local paths | Windows username and project/temp paths in receipts and `docs/decisions.md` | No secret value. Retained so frozen evidence stays byte-identical. |
| Third-party emails | Package-maintainer addresses inside saved PyPI/OSV metadata | Public package metadata. Accepted. |
| IPv4-like strings | Version numbers and `192.0.2.1` (documentation range) | Pass |
| Screenshots and fixtures | Constructed text; images have no text/EXIF chunks or GPS data | Pass |
| Server defaults | Binds `127.0.0.1`, rejects other Host headers, no CORS | Pass for local single-user use |
| Model loading | `model.safetensors`, `local_files_only=True`; no pickle, `eval`, `shell=True` or `trust_remote_code` | Pass |
| Workflows | No GitHub Actions workflows exist | Nothing to review; no CI |
| Licensing | Litmus MIT. RAID dataset card: MIT. Qwen2.5-0.5B and -Instruct: Apache-2.0. Neither dataset text nor weights are committed | Pass |
| Dependency advisories | Issue #1 remains open: model-stack packages have advisory matches | Disclosed. Not a visibility blocker; the release is still not security-cleared. |
| Claims | README headline metrics match `eval/results/r1g/metrics.json` exactly | Pass |

## Checks run for this audit

On Windows, Python 3.13.7, in a fresh model-free environment created from a
fresh clone (`pip install .` plus the pinned pytest/ruff versions):

- `pip check`: no broken requirements. `ruff check .`: all checks passed.
- `pytest`: 752 passed, 6 deselected (`slow`). Four modules that import `torch`
  were excluded because the model stack was not installed:
  `test_binoculars_math`, `test_profile_validation`, `test_r1a_models`,
  `test_r1b1_real`. No GPU or model-dependent test ran.
- `scripts/verify_r1_release.py --metrics` from an LF clone: `PASS`
  (3,361 rows, 675 groups, metrics reassembly and strict journal PASS,
  metrics SHA-256 `78e84cae8044d8bfec88c859fbfb245eb070d725e1a090d1d8691106330d02e5`).

The same verifier failed with `source_or_evidence_changed:src/litmus/cli.py`
in a clone made with Git for Windows' default `core.autocrlf=true`, because
CRLF conversion changes the hashed bytes. INSTALL now says to clone with
`core.autocrlf=false` for verification. No frozen file was changed.

## Changes for public visibility

Statements that described the repository as private were updated in README,
SECURITY, INSTALL, PORTFOLIO and the R1 release notes. Dated historical
records (decisions, plans, readiness reviews) keep their original wording.

## Not established

Exhaustive secret absence, exploitability of the dependency advisories, OS or
native network isolation, and any result beyond the frozen evaluation.
