# Filelock path follow-up — 2026-11-02

Inspected the existing installed huggingface_hub 0.36.2 and filelock 3.32.3
source, without executing model loading or downloads. This supplements the
earlier triage; it does not clear issue #1.

In huggingface_hub/utils/_fixes.py:87–119, WeakFileLock creates FileLock and
falls back to SoftFileLock after a specific NotImplementedError. The wrapper
is called from file_download.py:1167,1174,1295,1302. In filelock/__init__.py:57,
the Windows FileLock alias selects WindowsFileLock. Thus Windows locking and
its advisory conditions need investigation; the absence of direct Litmus
imports does not establish that the dependency is unused.

No ReadWriteLock or StrictSoftFileLock call was found in this inspected wrapper.
This narrows that wrapper's paths only; it is not proof about every transitive
caller, other operating systems or adversarial filesystem conditions. No exploit
was executed. No frozen source or dependency was modified.

The separate model-free demo has neither filelock nor huggingface_hub installed.
Its clean scan does not resolve their findings in the optional research stack.
Next work should isolate candidate upgrades and document compatibility before
any scientific-profile migration, calibration or use of an accepted threshold.
