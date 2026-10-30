"""R1-D2 constructed SDK outputs -> tests/fixtures/c2pa/constructed/.

CONSTRUCTED, NOT REAL SDK OUTPUT. Each file takes a committed real capture
(eval/results/r1d1_library_outputs/) and edits its status entries to show a
state no real R1-D1 fixture produces (no TSA may be used, so no real time
stamps exist). Each file states what was changed, the real capture it was
derived from, and the specification section or Litmus policy it represents.
Constructed outputs never count as evidence that the SDK emits a code.

    .venv\\Scripts\\python.exe scripts\\make_c2pa_constructed.py
"""
import copy
import json
import pathlib
import sys

from litmus.c2pa.mapping import CODES

ROOT = pathlib.Path(__file__).resolve().parent.parent
REAL = ROOT / "eval" / "results" / "r1d1_library_outputs"
OUT = ROOT / "tests" / "fixtures" / "c2pa" / "constructed"
SPEC_14_8 = ("C2PA 2.5 \u00a714.8 'Validate the time stamp' "
             "(https://spec.c2pa.org/specifications/specifications/2.5/specs/"
             "C2PA_Specification.html#_validate_the_time_stamp); cited per Ryan's "
             "partial implementation; section/text UNVERIFIED in this session")
POLICY_STRICT = ("Litmus mapping policy (docs/plans/R1-D-PLAN.md \u00a7c strictness "
                 "rules); not a C2PA specification requirement")
POLICY_ATTRIBUTION = ("Litmus attribution policy (docs/plans/R1-D-PLAN.md \u00a7p "
                      "Correction 1); the C2PA section defining this code was not "
                      "checked offline (UNVERIFIED)")
UNKNOWN_LABEL = "urn:c2pa:00000000-0000-0000-0000-000000000000"


def real_store(name):
    return json.loads((REAL / name).read_text(encoding="utf-8"))["manifest_store"]


def entry(store, code, path="c2pa.signature", label=None):
    label = label or store["active_manifest"]
    return {"code": code, "url": f"self#jumbf=/c2pa/{label}/{path}",
            "explanation": "CONSTRUCTED entry (not SDK output)"}


def active_lists(store):
    return store["validation_results"]["activeManifest"]


def build():
    out = {}

    def add(name, derived_from, represents, change, edit):
        store = copy.deepcopy(real_store(derived_from))
        edit(store)
        out[name] = {"constructed": True,
                     "note": "CONSTRUCTED, NOT REAL SDK OUTPUT",
                     "derived_from": ("eval/results/r1d1_library_outputs/"
                                      f"{derived_from}"),
                     "represents": represents, "change": change,
                     "manifest_store": store}

    trusted = "trusted_signer_jpg__production.json"

    def ts_ok(store):
        active_lists(store)["success"] += [entry(store, "timeStamp.trusted"),
                                           entry(store, "timeStamp.validated")]

    add("timestamp_trusted_validated.json", trusted, SPEC_14_8,
        "added timeStamp.trusted and timeStamp.validated (success)", ts_ok)

    for code in ("timeStamp.malformed", "timeStamp.mismatch", "timeStamp.untrusted",
                 "timeStamp.outsideValidity"):
        def ts_bad(store, code=code):
            active_lists(store)["informational"].append(entry(store, code))
        add(f"timestamp_ignored_{code.split('.', 1)[1]}.json", trusted, SPEC_14_8,
            f"added {code} (informational)", ts_bad)

    def outside(store):
        lists = active_lists(store)
        lists["success"] = [e for e in lists["success"]
                            if e["code"] != "claimSignature.insideValidity"]
        lists["failure"].append(entry(store, "claimSignature.outsideValidity"))

    add("claim_signature_outside_validity.json", trusted, SPEC_14_8,
        "replaced claimSignature.insideValidity (success) with "
        "claimSignature.outsideValidity (failure)", outside)

    def unmapped_integrity(store):
        active_lists(store)["success"].append(entry(
            store, "assertion.litmusConstructed.unrecognized",
            "c2pa.assertions/c2pa.hash.data"))

    add("unmapped_integrity_code.json", trusted, POLICY_STRICT,
        "added unrecognized code assertion.litmusConstructed.unrecognized (success)",
        unmapped_integrity)

    def unmapped_family(store):
        active_lists(store)["informational"].append(
            entry(store, "litmusConstructed.unknownFamily"))

    add("unmapped_unknown_family_code.json", trusted, POLICY_STRICT,
        "added unrecognized code litmusConstructed.unknownFamily (informational)",
        unmapped_family)

    def unattributable_label(store):
        active_lists(store)["failure"].append(entry(
            store, "claimSignature.mismatch", label=UNKNOWN_LABEL))

    add("unattributable_code_unknown_label.json", trusted, POLICY_ATTRIBUTION,
        f"added claimSignature.mismatch (failure) whose URL names {UNKNOWN_LABEL}, "
        "a manifest not in the store", unattributable_label)

    def unattributable_no_url(store):
        active_lists(store)["informational"].append(
            {"code": "assertion.hashedURI.match",
             "explanation": "CONSTRUCTED entry without a url (not SDK output)"})

    add("unattributable_code_no_url.json", trusted, POLICY_ATTRIBUTION,
        "added assertion.hashedURI.match (informational) with no url",
        unattributable_no_url)

    add("integrity_invalid_with_timestamp.json", "tampered_jpg__production.json",
        SPEC_14_8, "added timeStamp.trusted and timeStamp.validated (success) to "
        "the real tampered output (assertion.dataHash.mismatch)", ts_ok)

    ingredient = "ingredient_ai_only_jpg__production.json"

    def active_mismatch(store):
        active_lists(store)["failure"].append(entry(
            store, "assertion.action.ingredientMismatch",
            "c2pa.assertions/c2pa.actions.v2"))

    add("active_ingredient_mismatch.json", ingredient, POLICY_ATTRIBUTION,
        "added assertion.action.ingredientMismatch (failure) on the ACTIVE "
        "claim's c2pa.actions.v2 assertion", active_mismatch)

    def ingredient_mismatch(store):
        ing_label = store["manifests"][store["active_manifest"]][
            "ingredients"][0]["active_manifest"]
        delta = store["validation_results"]["ingredientDeltas"][0]["validationDeltas"]
        delta["failure"].append({"code": "ingredient.manifest.mismatch",
                                 "url": f"self#jumbf=/c2pa/{ing_label}",
                                 "explanation": "CONSTRUCTED entry (not SDK output)"})

    add("ingredient_manifest_mismatch.json", ingredient, POLICY_ATTRIBUTION,
        "added ingredient.manifest.mismatch (failure) in ingredientDeltas, "
        "URL naming the ingredient manifest", ingredient_mismatch)
    # Minimal stores for exhaustive mapping-row coverage. Synthetic injection
    # demonstrates Litmus policy only, never actual SDK emission.
    cases = {}
    positive = {"binding_match", "evidence", "ts_ok", "trusted"}
    for code, (_, effect) in CODES.items():
        label = "urn:c2pa:constructed-mapping-row"
        store = {"active_manifest": label,
                 "manifests": {label: {"assertions": []}},
                 "validation_results": {"activeManifest": {
                     "success": [], "informational": [], "failure": []}}}
        active_lists(store)["success"] = [entry(store, c) for c in (
            "assertion.dataHash.match", "claimSignature.validated",
            "claimSignature.insideValidity")]
        bucket = "success" if effect in positive else "failure"
        active_lists(store)[bucket].append(entry(store, code))
        cases[code] = store
    out["mapping_rows.json"] = {
        "constructed": True, "note": "CONSTRUCTED, NOT REAL SDK OUTPUT",
        "represents": POLICY_STRICT,
        "change": "minimal synthetic stores; one injected code per mapping row",
        "cases": cases}
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, record in build().items():
        (OUT / name).write_text(json.dumps(record, indent=1) + "\n",
                                encoding="utf-8", newline="\n")
        print(f"{name}: {record['change']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
