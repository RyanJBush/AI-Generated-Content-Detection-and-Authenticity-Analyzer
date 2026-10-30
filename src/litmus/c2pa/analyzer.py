"""Production image evidence adapter; imported only for accepted opt-in images."""
import time
from dataclasses import asdict

from litmus.c2pa.mapping import MAPPING_VERSION
from litmus.c2pa.metadata import summarize
from litmus.c2pa.pipeline import analyze_c2pa
from litmus.c2pa.reader import PINNED_C2PA_PYTHON, PINNED_SDK, installed_versions
from litmus.c2pa.rules import RuleInput, evaluate_rules
from litmus.c2pa.settings import production_config
from litmus.c2pa.trust_list import load_production_trust_list
from litmus.errors import C2paUnavailable
from litmus.schemas import OriginEvidence, OriginResult

METHOD_VERSION = "1"
# Reviewed D1/D2 evidence through 0c6fa08. This is a release prerequisite,
# not a runtime connectivity probe or a claim of network isolation.
REVIEWED_OFFLINE_EVIDENCE = True
REPORT_LIMITATIONS = [
    "C2PA results describe provenance metadata, not image content.",
    "Absence of Content Credentials is not evidence of human origin.",
    "Offline: remote manifests are not fetched.",
    "SDK trust observations are separate from Litmus production trust policy.",
    "Project timestamp evidence is constructed; real TSA validation has not "
    "been demonstrated.",
]


def analyze_image(data: bytes, mime: str) -> OriginEvidence:
    started = time.perf_counter()
    if not REVIEWED_OFFLINE_EVIDENCE:
        raise C2paUnavailable("C2PA offline evidence prerequisite is unavailable")
    try:
        trust = load_production_trust_list()
        config = production_config()
        versions = installed_versions()
        if versions != (PINNED_C2PA_PYTHON, PINNED_SDK):
            raise ValueError("library versions differ from reviewed offline evidence")
    except Exception as exc:
        raise C2paUnavailable(f"C2PA initialization failed: {exc}") from None

    try:
        outcome = analyze_c2pa(data, mime, config=config)
    except Exception as exc:
        # A malformed SDK payload or discovery failure must not discard the
        # report. The D2 engine still supplies rule 2, without invented states.
        outcome = evaluate_rules(RuleInput(
            True, "error", [f"c2pa_exception:{type(exc).__name__}"]))

    details = dict(outcome.details)
    mapped = details.pop("mapped", None)
    presence = {"store": "embedded", "no_credentials": "none",
                "remote_reference_only": "remote_reference_only"}.get(
                    details.get("read_kind"))
    provenance = {
        "manifest_present": presence,
        "active": asdict(mapped.active) if mapped else None,
        "ingredients": [asdict(r) for r in mapped.ingredients] if mapped else [],
        "mapping_version": MAPPING_VERSION,
        "trust_list": {"name": trust.name, "version": trust.version,
                       "sha256": trust.sha256, "anchor_count": len(trust.anchors)},
        "library_versions": {"c2pa_python": versions[0], "sdk": versions[1]},
        "settings": config, "policy": "production",
        "unsigned_metadata": summarize(data),
    }
    details.update({
        "rule": outcome.rule,
        "validation_state": mapped.validation_state if mapped else None,
        "status_entries": mapped.status_entries if mapped else [],
        "unmapped_status_codes": mapped.unmapped_status_codes if mapped else [],
        "unattributed": mapped.unattributed if mapped else [],
        "other_manifests": [asdict(r) for r in mapped.records[1:]
                            if r.manifest_label not in mapped.ingredient_labels]
        if mapped else [],
        "settings_applied": details.get("settings_applied"),
    })
    details.setdefault("timings", {"read_seconds": None,
                                   "read_response_seconds": None})
    details["timings"]["response_seconds"] = time.perf_counter() - started
    details["timings"]["unit"] = "seconds"
    notes = []
    if not mapped:
        notes.append("Manifest validation details unavailable for this outcome.")
    if details["settings_applied"] is None:
        notes.append("Settings application is unconfirmed; settings lists the "
                     "requested configuration only.")
    details["availability_notes"] = notes
    return OriginEvidence(
        method_id="c2pa_provenance", method_version=METHOD_VERSION,
        result=OriginResult(outcome.result), provenance=provenance,
        reasons=outcome.reasons,
        limitations=list(dict.fromkeys(outcome.limitations + REPORT_LIMITATIONS)),
        details=details,
    )
