# R1-E data-preparation evidence

Only metadata, opaque dataset row/source IDs, hashes, counts and verification
records belong here. Raw CSV, SQLite indexes and selected text blobs stay in
ignored `data/raid/`. No generation, title or prompt strings are published here.

RAID: Dugan et al., *RAID: A Shared Benchmark for Robust Evaluation of
Machine-Generated Text Detectors*, ACL 2024, pages 12463–12492.
Official dataset: https://huggingface.co/datasets/liamdugan/raid.
Dataset card declares MIT; underlying source-corpus redistribution terms have
not been fully audited. Approved use is local evaluation preparation only,
without raw-text redistribution. Litmus's own license remains undecided.

The approved artifact is train.csv at revision
865cac74188466cb0c3b7574a10204007b57a459. `preflight.json` records the builder's
revision-specific API match. `acquisition.json` is written only after accepted
download length/SHA-256 verification; a partial file is never preparation input.

`primary/` and `repeat/` contain independent canonical scientific ledgers and
manifest envelopes. Their local text-blob references are relative to the
corresponding ignored prepared directory. Run telemetry/guard observations are
separate under eval/results/r1e_*.json and are not scientific identity inputs.
No detector scores, calibration thresholds or test-evaluation metrics are
created by R1-E. Future calibration additionally requires at least 200 eligible
development human texts after all exclusions and valid R1-F execution identity.
