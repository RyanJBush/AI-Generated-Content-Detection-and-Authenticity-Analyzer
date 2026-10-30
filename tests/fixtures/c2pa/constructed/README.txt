CONSTRUCTED, NOT REAL SDK OUTPUT.

Every JSON file in this directory is produced by
scripts/make_c2pa_constructed.py (R1-D2) and records "constructed": true.
Most files edit the status entries of a committed REAL capture in
eval/results/r1d1_library_outputs/ and record the capture, change and policy.
mapping_rows.json instead contains 45 minimal synthetic stores, one per code
in the mapping table. It tests policy, not SDK code emission.

- timestamp_trusted_validated, timestamp_ignored_*, claim_signature_outside_validity,
  integrity_invalid_with_timestamp: C2PA 2.5 section 14.8 "Validate the time
  stamp" is a reviewer-supplied citation. The builder did not independently
  fetch or verify the specification text. The timestamp/signature separation
  follows Ryan's correction 2 as Litmus policy. No real timestamp validation
  is demonstrated: all real fixtures were signed without a TSA.
- unmapped_integrity_code, unmapped_unknown_family_code: Litmus mapping
  policy (unrecognized codes -> not_checked), not a specification requirement.
- unattributable_code_unknown_label, unattributable_code_no_url,
  active_ingredient_mismatch, ingredient_manifest_mismatch: Litmus attribution
  policy (R1-D plan section p, Correction 1); the specification section
  defining these codes was not checked offline (UNVERIFIED).

Constructed outputs never count as evidence that the SDK emits a code.
