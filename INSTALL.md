# Install and run Litmus R1

Litmus is a single-user local application. Start with Windows and Python 3.13
(the verified environment); other platforms and hardware are not certified.
Git is needed to clone the repository and verify the historical evidence.

## Basic installation: no model weights required

In PowerShell, from the directory where you keep projects:

```powershell
git clone https://github.com/RyanJBush/litmus.git
cd litmus
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\python.exe -m litmus.local_ui
```

The private repository requires access through your GitHub account. Installation
downloads the declared package dependencies from the configured package index.
Open http://127.0.0.1:8765. Upload `tests/fixtures/inputs/quality.txt`, enable
content observations, and analyze. Download JSON to retain the report. Image
credentials also work without language-model weights; try the constructed
`tests/fixtures/c2pa/active_ai_declared.jpg` with C2PA enabled. Its signer trust
is unknown under the intentionally empty production anchor list.

All analysis options initially remain off. Leave text origin off until the model
setup below is complete. A missing model or unsupported input is not evidence
that content is human-made. Ctrl+C stops the server and waits for active work.
Use `--port 8767` if 8765 is occupied. Never expose the service through a public
proxy. `Start-Litmus.cmd` is the equivalent launcher after the environment exists.

## Optional text-origin setup

The accepted profile uses an NVIDIA GeForce RTX 4060 Laptop GPU, NVIDIA driver
572.60, PyTorch 2.6.0+cu124, Windows, and the pinned model/tokenizer revisions.
The full exact profile is recorded in `eval/freezes/r1f_freeze.json`. CPU
fallback is not supported. Matching only the GPU name is not enough to apply
the accepted calibration; Litmus checks the complete scoring configuration.

For source-checkout use, install the pinned environment and editable package:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe scripts\download_models.py
```

The model setup command downloads the two pinned Qwen models and verifies
their weight hashes. Model licenses apply separately. It writes
`models.manifest.json`; retain the committed original and inspect any diff
before proceeding. This command is for a new user's setup, not a prerequisite
to republish an already provisioned checkout. The publication verification
used existing local weights and made no model or dataset downloads.

Restart the UI after setup. The synthetic fixture
`eval/inputs/r1b2/len512_00.txt` can exercise text origin. Calibration flags
require an exact match to the accepted configuration. A different machine may
produce an uncalibrated/inconclusive result; this release does not authorize
recalibration or reuse of the held-out evaluation texts.

## Verify the installation

```powershell
.venv\Scripts\python.exe -m litmus.cli analyze tests/fixtures/inputs/quality.txt --quality on
.venv\Scripts\python.exe -m litmus.cli analyze tests/fixtures/c2pa/active_ai_declared.jpg --c2pa on
```

The CLI prints JSON. Origin evidence and quality observations remain separate.
To verify the saved scientific record from a full Git clone, without models or
raw dataset texts:

```powershell
.venv\Scripts\python.exe scripts\verify_r1_release.py --metrics
```

Do not use the retired evaluation scoring/recovery commands. A source ZIP lacks
the Git history needed by the scientific verifier. The dataset and weights are
deliberately absent from GitHub. See README for scientific limitations.

## What has actually been verified

The publication checks use a fresh source snapshot and an isolated installation
of its newly built wheel, with existing pinned dependencies supplied locally.
They verify package imports, UI upload/poll/report, content observations and
the default image report. Dependency downloads on a new machine have not been
tested. Synthetic CUDA reuse and native C2PA were checked through the real HTTP
interface on the accepted local machine, not on alternate hardware.
