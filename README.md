# Litmus

> **Status: PLANNING DRAFT v0.3 — nothing below is implemented.** This README describes a *proposed* project. Items marked **PROPOSED**, **PROVISIONAL**, or **OPEN** are not decided. No code, models, datasets, or results exist for this version. The retired text-only implementation is preserved in Git history at recovery tag `litmus-text-before-multimodal-2026-10-26` (reviewer-verified to resolve to `106a645`) and is not part of this version unless explicitly approved.

Litmus is a planned evidence-reporting tool for examining text, images, audio, video, and documents for signs of AI generation or manipulation.

## What Litmus will and will not do

Litmus reports **evidence**, not verdicts.

- **Origin evidence and content-quality observations are separate record types.** Origin evidence concerns *how content was produced* (a validated Content Credentials manifest, a calibrated detector result). Quality observations describe *what the content contains* (repeated phrases, hedges). Quality observations never affect origin results.
- **Inconclusive is a valid result,** always with a reason.
- **No uncalibrated score is presented as a probability.** Raw scores are labeled as scores. Flags appear only where the exact configuration has been calibrated on held-out development data.
- **Claims are limited to evaluated tasks.** Each modality has its own methods, evaluation, and limitations. There is no combined "AI percentage."
- **Mixed content is expected.** Documents are split into segments (text blocks, embedded images, audio tracks), each reported separately with its location in the original.
- **Absence is not evidence.** No Content Credentials, no metadata, or a low detector score does not mean human-made.
- **Local and offline.** Analysis runs on your machine with outbound connections blocked; models load only from local files; remote Content Credentials are not fetched. Analyzed content is never sent over the network.
- **Not for punitive decisions.** Detection methods have known false-positive and evasion problems. Do not use Litmus as the sole basis for academic, employment, legal, or moderation decisions.

## Planned releases (PROPOSED)

| Release | Scope | Effort (estimate) |
|---|---|---|
| R0 | Foundations: record schemas, segment ancestry/coordinates, ingestion limits, report format, test harness | 8–14 h |
| R1 | Text origin evidence (provisional zero-shot method, evaluated) + text quality observations + **image provenance** (Content Credentials: integrity, signature, signer trust, and declared AI use reported separately; a declaration from an untrusted signer is shown but not treated as evidence) | 25–40 h |
| R2 | **Image detection** (provisional method, evaluated) + PDF/DOCX documents | 30–50 h |
| R3 | Synthetic-speech audio detection, evaluated in-domain (out-of-domain set blocked pending license clarification) | 25–40 h |
| R4 | Video, limited to evaluated face-manipulation detection, plus the audio track via R3 | 40–70 h |
| | **Total (estimate)** | **128–214 h** |

**R1 checks image provenance only; it does not detect AI-generated images.** An image without Content Credentials gets an inconclusive result in R1.

R0 and R1 are specified in detail; R2–R4 are provisional outlines. Model choices are **provisional** until license, access, feasibility, and training-data-overlap checks pass. Several candidate datasets are licensed for non-commercial use only. See `SPEC.md`.

## Current status

- Implementation: **not started.**
- Evaluation results: **none.**
- Open decisions: `SPEC.md` §15.
- Corrections: `SPEC-v0.3-ADDENDUM-A.md` (governs where it differs from `SPEC.md`).

## License

**OPEN.** Not yet chosen. Third-party datasets and models carry their own terms (`SPEC.md` §17).
