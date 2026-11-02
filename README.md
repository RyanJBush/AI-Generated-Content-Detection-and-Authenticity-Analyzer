# Litmus

> **Status: R1 in progress.** R0 foundations, opt-in uncalibrated text scoring,
> text-quality observations and opt-in image provenance are implemented.
> R1-D image provenance is independently reviewed and closed. Approved R1-E
> RAID data preparation (R1-E) is independently reviewed and closed, with Ryan's
> narrow historical transfer-accounting exception. Original transfer-cap
> compliance remains unproven. R1-F calibration and its committed freeze are
> independently reviewed and closed. R1-G is proposed only; test access remains
> unauthorized.
> Later modalities and releases remain planned.
> The retired text-only implementation is preserved in Git history at
> `litmus-text-before-multimodal-2026-10-26` (`106a645`).

Litmus reports evidence about text and image provenance. Audio, video and
document analysis remain planned.

## What Litmus will and will not do

Litmus reports **evidence**, not verdicts.

- **Origin evidence and content-quality observations are separate record types.** Origin evidence concerns *how content was produced* (a validated Content Credentials manifest, a calibrated detector result). Quality observations describe *what the content contains* (repeated phrases, hedges). Quality observations never affect origin results.
- **Inconclusive is a valid result,** always with a reason.
- **No uncalibrated score is presented as a probability.** Raw scores are labeled as scores. Flags appear only where the exact configuration has been calibrated on held-out development data.
- **Claims are limited to evaluated tasks.** Each modality has its own methods, evaluation, and limitations. There is no combined "AI percentage."
- **Segment records.** Current text and image inputs produce one root segment.
  Mixed-document extraction is planned for a later release.
- **Absence is not evidence.** No Content Credentials, no metadata, or a low detector score does not mean human-made.
- **Local and offline settings.** Models load from local files. Python network
  and subprocess guards are active; C2PA uses native offline settings. Remote
  Content Credentials are not fetched. Paired loopback tests observed zero
  connections for the exercised remote fixtures/settings. Network isolation
  has not been demonstrated; Python guards do not intercept native networking.
- **Not for punitive decisions.** Detection methods have known false-positive and evasion problems. Do not use Litmus as the sole basis for academic, employment, legal, or moderation decisions.

## Text quality observations: limitations

Opt-in with `litmus analyze FILE --quality on` (default `off`).

- **No AI-origin claim.** Quality observations count surface patterns (stock phrases, hedges, repeated word 3-grams, claim phrases to inspect). They do not establish AI origin and never affect origin results.
- **English-oriented, provisional lexicons (v1).** The lexicons were drafted with AI assistance and reviewed by Ryan; their entries and counts are not evaluated against any corpus.
- **Word counts assume space-separated scripts.** Text without spaces (for example CJK) counts each run as one word, so rates are not comparable across scripts.
- **Lexicon licensing: OPEN — pending Ryan's decision.**

## Image provenance: opt-in and limitations

`litmus analyze IMAGE --c2pa on` enables C2PA evidence for accepted JPEG, PNG
and WebP images. The default is `--c2pa off`; omitted and explicit off retain
the existing image placeholder reports. Text-only inputs are unchanged.

Integrity, claim signature, signer trust, timestamp state and AI-use declaration
are reported separately for the active manifest and its referenced ingredients.
Unsigned EXIF fields and XMP presence/length are labeled **unverifiable; editable;
not evidence** and never affect origin results. EXIF DateTime is not verified
signing time.

**With an empty production trust list, signer_trust is unknown for every
manifest, so no C2PA result can be supports_ai in R1 under the production
policy.** A valid AI-use declaration alone yields inconclusive /
untrusted_signed_ai_declaration. Absence of credentials or declarations is not
evidence of human origin. R1 examines provenance, not AI-generated image content.

Project timestamp cases are **constructed**, not evidence of real TSA validation.
The reviewer supplied the [C2PA 2.5 section 14.8 citation](https://spec.c2pa.org/specifications/specifications/2.5/specs/C2PA_Specification.html#_validate_the_time_stamp);
the builder did not independently fetch or verify its text.

The 120-second C2PA deadline limits response waiting, not native execution.
A timed-out read continues on one worker; further requests return a busy error
until it finishes. A produced report exits 0 even if its analyzer record says
error. Missing activation evidence, invalid production trust resources, missing
SDK or versions differing from reviewed 0.38.0 / 0.91.0 prevent activation:
the CLI prints an error and exits 1 without writing a report.

See [interfaces](docs/interfaces.md) and [decisions](docs/decisions.md) for the
record contract, observed tests and remaining limits.

## Release roadmap (later work remains proposed)

| Release | Scope | Effort (estimate) |
|---|---|---|
| R0 | Foundations: record schemas, segment ancestry/coordinates, ingestion limits, report format, test harness | 8–14 h |
| R1 | Text origin evidence (provisional zero-shot method, evaluated) + text quality observations + **image provenance** (Content Credentials: integrity, signature, signer trust, and declared AI use reported separately; a declaration from an untrusted signer is shown but not treated as evidence) | 25–40 h |
| R2 | **Image detection** (provisional method, evaluated) + PDF/DOCX documents | 30–50 h |
| R3 | Synthetic-speech audio detection, evaluated in-domain (out-of-domain set blocked pending license clarification) | 25–40 h |
| R4 | Video, limited to evaluated face-manipulation detection, plus the audio track via R3 | 40–70 h |
| | **Total (estimate)** | **128–214 h** |

**R1 checks image provenance only; it does not detect AI-generated images.**
With C2PA enabled, an image without Content Credentials gets an inconclusive
result. With it off, the existing not-supported placeholder remains.

R0 and R1 are specified in detail; R2–R4 are provisional outlines. Model choices are **provisional** until license, access, feasibility, and training-data-overlap checks pass. Several candidate datasets are licensed for non-commercial use only. See `SPEC.md`.

## Current status

- Implementation: R0 foundations and R1 text/quality work are implemented;
  C2PA D1–D3 and R1-D are independently reviewed and closed. R1-E data preparation
  is independently reviewed and closed with 973 retained source groups (298 dev,
  675 test). R1-F scored 1,484 development rows successfully, including 298 valid
  human negatives. The calibration/freeze are independently reviewed and closed;
  no held-out test scoring or evaluation has occurred. R1-G-PLAN.md is proposed
  for review, not approved for execution.
  Ryan accepted the specific historical redirect-body accounting uncertainty;
  this is not proof that the original cumulative transfer met its 13 GB cap.
  The downloader correction was tested offline, with no further network requests.
  No scoring, calibration or test evaluation was performed in R1-E.
- Results: model-free tests, fixture observations and uncalibrated scorer
  benchmarks are recorded in `docs/decisions.md` and `eval/results/`.
  No image detector or calibrated text-origin decision is supplied.
- Open decisions: `SPEC.md` §15.
- Governing corrections: `R1-PLAN-CORRECTIONS-A.md`, `R1-PLAN.md`, the SPEC
  addenda and `docs/plans/R1-D-PLAN.md`, including its approved corrections.

## Development calibration (R1-F, independently reviewed)

The local CUDA/fp32 profile has a 5% empirical development calibration, bound to
the exact configuration hash in [the freeze](eval/freezes/r1f_freeze.json).
The scorer uses r=-raw_score and flags only r > -0.9272342324256897, equivalently
raw_score < 0.9272342324256897. Equality is not flagged. There were 14 exceedances
among 298 development-human negatives and one threshold tie; these are development
observations, not test FPR or a population guarantee. All 1,484 dev scores were
valid; the independent first-ten-human fresh-process audit matched exactly.

Configuration hash:
`10f0fa316fa5f3d87c7819f86f09ecedc5bc5b1b71e9250d8586aece7390db2f`.
Source implementation: `047421cf4c36f8a946453eacc1b9c056bf5147d6`.
CUDA preflights and development work reported zero Python connection/forbidden
data-access attempts. This does not demonstrate OS/native network isolation.
CPU is uncalibrated, 1% calibration stays disabled, and raw scores are not
probabilities. Updating source, driver, libraries or any hashed profile field
invalidates matching. Default CLI analysis remains a placeholder unless explicitly
enabled; default image reports and quality/origin separation are unchanged.

See [F verification](eval/results/r1f_verification.json) and
[the approved plan](docs/plans/R1-F-PLAN.md). Ryan supplied independent confirmation
of freeze commit `bf455659053cca15ec82cb85065613c6b7459a44`. The proposed
[R1-G plan](docs/plans/R1-G-PLAN.md) still requires approval before test access.

## License

**OPEN.** Not yet chosen. Third-party datasets and models carry their own terms (`SPEC.md` §17).
