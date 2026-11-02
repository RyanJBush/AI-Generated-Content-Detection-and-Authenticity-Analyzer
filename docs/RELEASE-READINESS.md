# Release preparation — 2026-11-02

## Decision

Merge the independently reviewed local UI improvements. Prepare a tagged **draft**
release for private review. Do not declare a security-cleared stable release or
change repository visibility. The user authorized the previously proposed merge,
release preparation, privacy/dependency review and portfolio materials.

## Current checks

Production browser upload, quality observations, disabled-origin explanation,
JSON export and same-tab reload all passed again on f11f6c5, using constructed
text. Original readiness evidence records 883 default tests inside/outside,
Ruff, pip check, installed-wheel verification and scientific identity checks.
No runtime code changed during this release-preparation step; those checks are
not represented as newly rerun. History scan found only the two documented test
signing keys, no other matched credentials and no prohibited dataset/model paths.

## Dependency advisory audit: unresolved release gate

Queried OSV for 37 installed Python packages, including the model/development
stack. No package was installed or upgraded. CUDA's local version suffix was
removed only for matching the PyPI torch release. Retained full machine-readable
query results and advisory records under eval/results/release/.

| Package | Installed | Matching advisory records |
|---|---|---:|
| filelock | 3.32.3 | 12 |
| pip | 25.2 | 12 |
| torch | 2.6.0+cu124 | 24 |
| transformers | 4.57.6 | 11 |

These 59 records are **46 distinct advisories after alias deduplication**, not
59 distinct vulnerabilities. Matches are version-based, not proof that Litmus
exposes every affected path. The dated [dependency-security
triage](security/dependency-triage-2026-11-02.md) records the affected/fixed
events, source URLs and retrieval date, current-path classifications and a
bounded remediation proposal. No critical severity claim or
absence-of-vulnerabilities claim follows from this audit. The remaining 33
packages had no returned match; that is not proof of safety or full database
coverage.

High-severity records include:
- [Transformers model-config code execution](https://github.com/advisories/GHSA-29pf-2h5f-8g72).
- [Transformers LightGlue model loading](https://github.com/advisories/GHSA-fgcw-684q-jj6r).
- [Transformers generation code download](https://github.com/advisories/GHSA-x9r9-c232-4q39).
- [Transformers template path traversal](https://github.com/advisories/GHSA-xrqw-3rrv-vx5w).
- [filelock SQLite lock paths](https://github.com/advisories/GHSA-v4x8-3wr5-3wq8).

Preliminary source assessment: Litmus loads pinned local causal-language models
with local_files_only and an explicit attention implementation. Its scorer does
not call Trainer, LightGlue, generate or save_pretrained. This reduces some
apparent exposure but is not a validated exploitability determination. A package
match must not be silently dismissed because normal paths appear different.
The filelock high-severity advisory concerns POSIX SQLite-backed locks; the
accepted environment is Windows, but other returned advisories cover Windows.
pip findings concern installation tooling. Native libraries/driver advisories
and transitive non-Python components were not audited.

Next security work must separately map each unique advisory to used paths and
choose supported patched versions in an isolated environment. Run compatibility,
input-boundary and model-free checks there. Any runtime change that alters the
frozen profile requires an explicitly approved new scientific protocol before
calibration or held-out access. Do not reuse the accepted threshold under a new
configuration or rewrite old evidence. No such upgrade is included in this task.

## Privacy and license review

MIT is present and matches package metadata. It covers Litmus's original code,
documentation and lexicons; it does not relicense models, datasets or dependencies.
RAID text and weights remain ignored/untracked; no raw texts were read for this
review. Test C2PA private keys are deliberately public synthetic test material,
locally generated and documented in tests/fixtures/c2pa/pki/README.txt, with no
real timestamp authority. They must never sign real assets. Screenshot/export
samples are explicitly constructed; no customer data is claimed.

The preserved Git history contains the author's personal email, and historical
receipts contain Windows username/project paths. These are retained, not secretly
redacted or rewritten. Keeping the repository private avoids an unapproved new
public disclosure. Before public visibility, the owner must decide whether to
publish this history as-is or authorize a separate sanitized publication design.
This is a practical scope review, not a comprehensive legal or privacy opinion.

## Remaining verification

Screen-reader operation and another physical computer/GPU remain **Not Tested**:
no second machine or independent assistive-technology session was available.
Existing keyboard/reflow/contrast checks are narrower evidence. A clean wheel
installed using this machine's existing dependencies is not a second-machine
install. Owner subjective usability feedback also cannot be supplied by an agent.
Public hosting remains outside scope; no external service deployment was made.

## Reproduction

The OSV query endpoint is https://api.osv.dev/v1/querybatch. Send one queries
entry per installed package, each with package.name, package.ecosystem=PyPI and
version. The retained receipt lists every submitted package/version and returned
ID; details were fetched from https://api.osv.dev/v1/vulns/{ID}. Only package
identities were sent, no source, dataset, model or credentials. Check the receipt's
UTC timestamp: advisory results can change. This audit does not add a dependency.

See [portfolio presentation](PORTFOLIO.md), [draft release notes](RELEASE-NOTES-R1.md)
and [earlier executable evidence](../eval/results/readiness/VERIFICATION.md).
