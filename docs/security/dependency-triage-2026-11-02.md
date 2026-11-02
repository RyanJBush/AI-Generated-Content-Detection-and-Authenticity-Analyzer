# Dependency-security triage — 2026-11-02

Status: **release gate unresolved; analysis only**. This document does not
upgrade dependencies, change the application, or clear the draft release.

## Scope and evidence

The saved OSV query covered 37 installed Python packages at
`2026-11-02T17:59:11.463602Z`, using
[`https://api.osv.dev/v1/querybatch`](https://api.osv.dev/v1/querybatch).
Per-advisory records are retained in
[`dependency-advisories.json`](../../eval/results/release/dependency-advisories.json)
and [`advisory-details.json`](../../eval/results/release/advisory-details.json).
Each detail record also retains its advisory references and affected-version
events; the canonical detail URL is
`https://api.osv.dev/v1/vulns/{GHSA-or-PYSEC-id}`.

The 59 returned records collapse to **46 distinct advisories** by joining IDs
that share a GHSA, CVE, PYSEC or vendor alias:

| Package | Installed | Records | Distinct advisories |
|---|---:|---:|---:|
| filelock | 3.32.3 | 12 | 12 |
| pip | 25.2 | 12 | 6 |
| torch | 2.6.0+cu124 | 24 | 22 |
| transformers | 4.57.6 | 11 | 6 |
| **Total** |  | **59** | **46** |

An attempted live OSV detail lookup on this review run failed with DNS/network
unavailability (`api.osv.dev` could not be resolved). The affected/fixed
versions below therefore mean **the saved OSV snapshot**, not a fresh 2026-11-02
refresh. No exploit payloads were executed and no private source, data, model
weights or credentials were sent to a scanner.

## Execution-path evidence

* The production model loader sets `HF_HUB_OFFLINE=1` and
  `TRANSFORMERS_OFFLINE=1` before importing the model libraries, then calls
  `AutoTokenizer.from_pretrained(..., local_files_only=True)` and
  `AutoModelForCausalLM.from_pretrained(..., local_files_only=True)` with local
  files only ([`loader.py:271-296`](../../src/litmus/scorer/loader.py#L271-L296)).
* Required local assets include `config.json`, `model.safetensors` and tokenizer
  files ([`loader.py:24-25`](../../src/litmus/scorer/loader.py#L24-L25)).
  The setup-only downloader uses pinned Hugging Face revisions
  ([`download_models.py:52-64`](../../scripts/download_models.py#L52-L64)) and
  hashes the model safetensors file ([`download_models.py:75-82`](../../scripts/download_models.py#L75-L82)).
* No production use of `torch.load`, `Trainer`, LightGlue, custom generation
  loading, `generate`, `save_pretrained`, JIT scripting, Inductor compilation,
  or the listed affected tensor operations was found in the reviewed path.
* `filelock` is transitive through `huggingface_hub`, torch and transformers
  ([`requirements.lock:10`](../../requirements.lock#L10)); the application does
  not import it directly. `pip` is installation/verification tooling, not an
  application runtime dependency ([`INSTALL.md:15-46`](../../INSTALL.md#L15-L46)).

These observations reduce some paths but do not turn a package-version match
into proof of safety. Offline operation does not dismiss setup-time, local
filesystem, malformed-model, or future-path exposure.

## Deduplicated findings inventory

The `Affected event` column is the saved OSV range event (`introduced`,
`last_affected`, or `fixed`). A fixed value is a remediation floor for that
record, not a proposed lockfile change. Each row is classified against the
current Litmus path:

* **Potentially exposed** — the package/API or setup path is present, but the
  attacker-controlled precondition was not demonstrated.
* **Apparently outside current execution path** — the installed version matches,
  but the affected API, platform or input path was not found in current use.
* **Unresolved** — evidence is insufficient to classify the current path.

| Package | Advisory aliases (canonical GHSA first) | Affected event | Fixed | Classification |
|---|---|---|---|---|
| transformers | GHSA-29pf-2h5f-8g72 / CVE-2026-4372 / PYSEC-2026-2289 | introduced 0 | 5.3.0 | Potentially exposed: the vulnerable `from_pretrained` API is used, although local-only pinned loading was observed. |
| transformers | GHSA-69w3-r845-3855 / CVE-2026-1839 / PYSEC-2026-2288 | introduced 0 | 5.0.0rc3 | Apparently outside: `Trainer` is not used. |
| transformers | GHSA-fgcw-684q-jj6r / CVE-2026-5241 / PYSEC-2026-2290 | introduced 0 | 5.5.0 | Apparently outside: LightGlue is not used. |
| transformers | GHSA-x9r9-c232-4q39 / CVE-2026-80047 / PYSEC-2026-4174 | 4.49.0–5.8.1 | not recorded | Apparently outside: custom generation loading is not used. |
| transformers | GHSA-xrqw-3rrv-vx5w / CVE-2026-9856 / PYSEC-2026-3929 | introduced 0 | 5.10.0 | Apparently outside: `save_pretrained` is not used. |
| transformers | PYSEC-2025-217 / CVE-2025-14929 | last affected 5.0.0-rc0 | not recorded | Apparently outside: X-CLIP conversion is not used. |
| torch | GHSA-3749-ghw9-m3mg / CVE-2025-2953 / PYSEC-2025-191 | introduced 0 | 2.7.1-rc1 | Apparently outside: affected local DoS operation was not found. |
| torch | GHSA-887c-mr87-cxwp / CVE-2025-3730 / PYSEC-2026-1970 | introduced 0 | 2.8.0 | Apparently outside: affected resource-shutdown path was not found. |
| torch | GHSA-c678-jfcj-6jmf / CVE-2025-2148 / PYSEC-2025-189 | last affected 2.6.0 | not recorded | Apparently outside: tuple-handler path was not found. |
| torch | GHSA-f4hp-rmr7-r7v8 / CVE-2025-2998 / PYSEC-2025-192 | last affected 2.6.0 | not recorded | Apparently outside: affected memory-consumption path was not found. |
| torch | GHSA-qfhq-4f3w-5fph / CVE-2025-3001 / PYSEC-2025-195 | introduced 0 | 2.10.0 | Apparently outside: `torch.lstm_cell` is not used. |
| torch | GHSA-rrmf-rvhw-rf47 / CVE-2025-3000 / PYSEC-2025-194 | introduced 0 | 2.13.0 | Apparently outside: `torch.jit.script` is not used. |
| torch | GHSA-vgrw-7cvw-pwgx / CVE-2025-2999 / PYSEC-2025-193 | introduced 0 | 2.9.1 | Apparently outside: `unpack_sequence` is not used. |
| torch | GHSA-x3gm-94wq-g975 / CVE-2025-2149 / PYSEC-2025-190 | last affected 2.6.0 | not recorded | Apparently outside: affected quantized sigmoid path was not found. |
| torch | PYSEC-2025-198 / CVE-2025-46148 | introduced 0 | 2.7.0 | Apparently outside: `PairwiseDistance` is not used. |
| torch | PYSEC-2025-199 / CVE-2025-46149 | 2.6.0–<2.7.0 | 2.7.0 | Apparently outside: affected Inductor/Fold path is not used. |
| torch | PYSEC-2025-200 / CVE-2025-46150 | 2.6.0–<2.7.0 | 2.7.0 | Apparently outside: affected compiled pooling path is not used. |
| torch | PYSEC-2025-201 / CVE-2025-46152 | 2.6.0–<2.7.0 | 2.7.0 | Apparently outside: affected bitwise path is not used. |
| torch | PYSEC-2025-202 / CVE-2025-46153 | 2.6.0–<2.7.0 | 2.7.0 | Apparently outside: affected dropout decomposition is not used. |
| torch | PYSEC-2025-203 / CVE-2025-55551 | introduced 0 | 2.9.0 | Apparently outside: affected Inductor/linear-algebra path is not used. |
| torch | PYSEC-2025-204 / CVE-2025-55552 | introduced 0 | 2.9.0 | Apparently outside: affected operation combination is not used. |
| torch | PYSEC-2025-205 / CVE-2025-55553 | introduced 0 | 2.7.1 | Apparently outside: affected Inductor path is not used. |
| torch | PYSEC-2025-206 / CVE-2025-55554 | introduced 0 | 2.9.0 | Apparently outside: affected conversion path is not used. |
| torch | PYSEC-2025-207 / CVE-2025-55557 | introduced 0 | 2.7.1 | Apparently outside: affected compiled operation chain is not used. |
| torch | PYSEC-2025-208 / CVE-2025-55558 | introduced 0 | 2.7.1 | Apparently outside: affected compiled operation chain is not used. |
| torch | PYSEC-2025-209 / CVE-2025-55560 | introduced 0 | 2.7.1 | Apparently outside: affected sparse/dense conversion is not used. |
| torch | PYSEC-2026-139 / CVE-2026-4538 | last affected 2.10.0 | not recorded | Apparently outside: local PT2 deserialization is not used. |
| torch | PYSEC-2026-2286 / CVE-2026-24747 / GHSA-63cw-57p8-fm3p / PYSEC-2026-1856 | introduced 0 | 2.10.0 | Apparently outside: production uses safetensors, not pickle checkpoints. |
| filelock | GHSA-567q-5qvw-pf92 / CVE-2026-112907 | 3.22.0–<4.2.1 | 4.2.1 | Potentially exposed during setup on Windows/shared local filesystems. |
| filelock | GHSA-6627-m3xw-93mp / CVE-2026-112908 | 3.30.0–<4.2.1 | 4.2.1 | Potentially exposed during setup on Windows/shared local filesystems. |
| filelock | GHSA-69hj-f68j-2879 / CVE-2026-112909 | introduced 0 | 4.2.1 | Potentially exposed during setup on hostile local filesystems. |
| filelock | GHSA-8mx5-7m5m-r77g / CVE-2026-112910 | 3.10.0–<4.2.1 | 4.2.1 | Potentially exposed during setup on Windows/shared local filesystems. |
| filelock | GHSA-9c4x-gm8v-wgc4 / CVE-2026-112911 | 3.30.0–<4.2.1 | 4.2.1 | Potentially exposed during setup on shared local filesystems. |
| filelock | GHSA-9vhv-jxww-xfm5 / CVE-2026-112913 | 3.20.4–<4.2.1 | 4.2.1 | Potentially exposed during setup on Windows/shared local filesystems. |
| filelock | GHSA-cwqr-hh33-gh44 / CVE-2026-112915 | 3.20.4–<4.2.1 | 4.2.1 | Potentially exposed during setup; stall/DoS path not demonstrated. |
| filelock | GHSA-fq56-3cx3-fjxp / CVE-2026-112935 | 3.22.0–<4.2.1 | 4.2.1 | Potentially exposed during setup on hostile local filesystems. |
| filelock | GHSA-j8f7-rjxc-mr56 / CVE-2026-112936 | 3.20.4–<4.0.9 | 4.0.9 | Potentially exposed during setup on shared local filesystems. |
| filelock | GHSA-m462-7rxw-wvpg / CVE-2026-112938 | 3.30.0–<4.2.1 | 4.2.1 | Potentially exposed during setup on shared local filesystems. |
| filelock | GHSA-rfpc-qcw5-3pc4 / CVE-2026-112939 | 3.22.0–<4.2.1 | 4.2.1 | Potentially exposed during setup on hostile local filesystems. |
| filelock | GHSA-v4x8-3wr5-3wq8 / CVE-2026-112940 | 3.20.4–<4.2.1 | 4.2.1 | Potentially exposed during setup; SQLite lock integrity path needs transitive tracing. |
| pip | GHSA-4xh5-x5gv-qwph / CVE-2025-8869 / PYSEC-2026-1795 | introduced 0 | 25.3 | Apparently outside: installation tooling only. |
| pip | GHSA-58qw-9mgm-455v / CVE-2026-3219 / PYSEC-2026-2875 | introduced 0 | 26.1 | Apparently outside: installation tooling only. |
| pip | GHSA-6vgw-5pg2-w6jp / CVE-2026-1703 / PYSEC-2026-1796 | introduced 0 | 26.0 | Apparently outside: installation tooling only. |
| pip | GHSA-jp4c-xjxw-mgf9 / CVE-2026-6357 / PYSEC-2026-2876 | introduced 0 | 26.1 | Apparently outside: installation tooling only. |
| pip | GHSA-qwm4-qh6w-59xr / CVE-2026-13346 / PYSEC-2026-3721 | introduced 0 | 26.2.0 | Apparently outside: installation tooling only. |
| pip | GHSA-wf93-45jw-7689 / CVE-2026-8643 / PYSEC-2026-196 | introduced 0 | 26.1.2 | Apparently outside: installation tooling only. |

No finding is classified as confirmed exposure from the reviewed current path.
That is not a security clearance: the Transformers model-config finding remains
potentially exposed because its loading API is present, filelock setup behavior
is not fully traced through every transitive call, and the live advisory source
could not be refreshed.

## Bounded remediation proposal

### 1. Basic model-free package

Keep the basic package (`pillow`, `c2pa-python`) separate from the optional
model stack. Do not add a runtime dependency solely to silence advisory tooling.
Re-run the model-free tests, wheel import/UI checks, `ruff`, `pip check`, and
the saved-report checks in an isolated candidate environment.

### 2. Optional model stack

Evaluate, without changing the accepted lock, a candidate stack at least at
`transformers>=5.10.0`, `torch>=2.10.0`, and `filelock>=4.2.1`, subject to
available CUDA 12.4 wheels and supported Python 3.13 APIs. Verify offline
local-only loading, all pinned model files and tokenizer hashes, report schema,
deterministic settings, and model-free behavior. The broadest fixed floors are
not automatically compatible with the R1 CUDA wheel or the frozen scorer.

Any change to torch, transformers, tokenizer behavior, model loading, numerical
settings or source identity is a **new execution profile**. It requires an
explicitly reviewed migration protocol, a new calibration decision and fresh
validation before any threshold or held-out evidence could be used. The
accepted calibration must never be reused under the candidate profile.

### 3. Development/install tooling

Evaluate `pip>=26.2` independently for archive/index safety and record the
installer version used to construct the candidate environment. Do not treat
pip findings as application-runtime exposure, and do not enable automatic
upgrades. Trace the exact `filelock` calls made by `huggingface_hub` during
setup on the supported Windows profile and on any shared filesystem before
classifying those paths as cleared.

### 4. Release decision

For a candidate remediation, record the new OSV query URL, UTC retrieval time,
all aliases, package metadata, compatibility failures and remaining findings.
Run only constructed/model-free and authorized local checks; do not download
new weights, access held-out text, rescore, recalibrate, alter thresholds, or
rewrite frozen evidence in this triage. The stable-release gate remains closed
until those approvals and checks exist. Historical transfer-accounting
compliance remains unproven, and legacy G interruption recovery remains
retired rather than repaired.
