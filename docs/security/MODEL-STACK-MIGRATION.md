# Model-stack migration candidate — proposed, not approved

## Verified preflight, 2026-11-02

Queried official PyPI metadata, OSV and the PyTorch CUDA 12.4 index. Extracted metadata fields and retrieval time are in eval/results/security-candidate/metadata-preflight.json.
No package was installed or upgraded during this preflight.

The earlier proposed torch 2.10.0 floor is insufficient: OSV returned
GHSA-rrmf-rvhw-rf47 and PYSEC-2026-139. That version is absent from the queried
CUDA 12.4 index. A universal version floor must not be treated as compatibility.
PyPI currently lists torch 2.15.0 with a CPython 3.13 Windows wheel; its OSV
query returned no matches. transformers 5.10.0, filelock 4.2.7 and pip 26.2.2
also returned no matches. These are direct-package metadata results only.

The accepted CUDA profile cannot be preserved merely by replacing these version
numbers. No new runtime is approved by this document, and no package is claimed
compatible with the existing GPU driver, model loader or calibration.

## Bounded next implementation

1. Create a new ignored candidate environment, preserving .venv and .venv-ui.
   Resolve the candidate dependencies and save full package metadata, wheel
   identities, platform tags, CUDA runtime and driver requirements before installation.
   Requery the entire resolved environment, not just the four direct candidates.
2. Verify the installed GPU driver supports the selected wheel's CUDA runtime.
   Stop on incompatibility. Do not update the driver, substitute CPU execution,
   silently change precision or download alternative model weights.
3. Run model-free compatibility checks in that environment: report serialization,
   CLI/UI defaults, error behavior, wheel imports and dependency consistency.
   Validate source/configuration mismatch rejection before loading model assets.
4. Propose loader/API adaptations outside the accepted frozen source identities,
   with a separately named execution profile and constructed numerical tests.
   Any required frozen-source change must be reviewed before implementation.
5. Stop for review with full candidate identities and actual failures/results.
   Installation success and zero advisory matches do not establish calibration.

## Separate scientific authorization

No candidate may use the accepted threshold as its own calibrated threshold.
Any decision to enable text-origin reporting under a new profile requires a
separately approved calibration protocol and release decision. Original held-out
test texts remain unavailable for this migration; do not reuse them as a tuning
or compatibility set. Preserve all historical calibration, ledgers and receipts.

## Release path while migration is pending

The separate model-free demo can show content observations and constructed image
credentials using its tested environment. Keep text-origin off there. The draft
release and issue #1 stay open until their explicitly scoped security criteria
are accepted. Screen-reader speech and second-machine checks remain separate
requirements; this metadata preflight does not fulfill them.


## Platform correction — retrieved 2026-11-03T01:05:32.788118+00:00

The prior PyPI Windows wheel observation did not establish CUDA support. Its
dependency metadata applies NVIDIA CUDA dependencies to Linux; that alone is
not an inspection of the Windows wheel's binary contents. Do not use the PyPI
filename as evidence of a usable GPU candidate.

The official [cu132 index](https://download.pytorch.org/whl/cu132/torch/) lists
torch-2.15.0+cu132-cp313-cp313-win_amd64.whl. NVIDIA's
[driver compatibility table](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html#cuda-driver)
requires driver >=580 for CUDA 13.x minor-version compatibility. The recorded
572.60 driver does not meet that floor. This candidate fails the existing
no-driver-update boundary. The [cu126 index](https://download.pytorch.org/whl/cu126/torch/)
lists torch-2.14.1+cu126-cp313-cp313-win_amd64.whl. That is an alternative for
future investigation, not an approved or tested replacement.

Extracted metadata, source URLs and retrieval time are retained in
platform-followup.json beside the original receipt. No wheel was downloaded or
executed; full transitive compatibility and a new advisory scan of that alternative
remain outstanding. PROFILE_FIELDS in src/litmus/scorer/identity.py includes
driver, CUDA and library versions, so any replacement needs a new identity.
A future calibration/evaluation protocol must use newly collected held-out data
for a new final evaluation, not recycle the original test set for tuning.
