"""C2PA SDK output -> per-manifest records (R1-D2; R1-D plan §b, §c, §p).

Input: the manifest store JSON returned by ``Reader.json()`` (installed
c2pa-python 0.38.0 / SDK 0.91.0), as captured in
eval/results/r1d1_library_outputs/. Output: one ``ManifestRecord`` per
manifest (active first), plus the store-level validation state and any
status entries that could not be attributed.

Attribution (§p Correction 1): every status entry is assigned to the manifest
named in its URL (``self#jumbf=/c2pa/<manifest label>/...``). An entry whose
URL is relative (no label) belongs to the manifest whose results list it was
found in. Codes on the active claim, including
``assertion.action.ingredientMismatch``, affect the active record; codes on an
ingredient manifest affect only that record. An entry whose manifest cannot be
determined (no URL, or a label not in the store) makes the active manifest's
integrity and signature ``not_checked``, with a note.

Fields (none implies another):

- integrity: active manifest from its content-binding / hashed-URI codes;
  ``valid`` needs a hard-binding ``*.match`` code and no invalid code.
  Ingredient manifests: never ``valid`` (their bindings refer to other
  assets); ``invalid`` if an integrity-invalid code is attributed to them.
- signature: claim-signature and signing-credential validity codes, excluding
  trust codes; ``valid`` needs ``claimSignature.validated`` and
  ``claimSignature.insideValidity`` and no invalid code.
- timestamp (Litmus policy; specification basis remains UNVERIFIED):
  ``trusted_validated``
  (both ``timeStamp.trusted`` and ``timeStamp.validated``, no ignored code) /
  ``ignored`` (a time-stamp failure code) / ``absent`` /
  ``not_checked`` (an unrecognized ``timeStamp.*`` code). A time-stamp
  failure alone never makes ``signature`` invalid.
- signing_time_basis: ``trusted_timestamp`` only when timestamp is
  ``trusted_validated``; ``current_time_check`` when the signature validity
  codes come from the current-time check; otherwise ``unknown``.
  ``claimSignature.insideValidity`` alone does not establish a verified
  signing time.
- signer_trust: decided by a ``TrustPolicy``. ``PRODUCTION_POLICY`` (the only
  policy defined in the package) always returns ``unknown``; SDK trust codes go
  only to ``sdk_trust_observation`` (diagnostic).
- declared_ai_use: ``declared`` only for an actions assertion whose
  ``digitalSourceType`` is exactly one of ``AI_SOURCE_TYPES``.

Any unrecognized code makes integrity and signature ``not_checked`` unless
already invalid (plan §c strictness rule 2).
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

MAPPING_VERSION = "1"

# Exact IPTC URIs; both strings occur verbatim in the installed SDK binary
# (c2pa/libs/c2pa_c.dll), and the first in the D1 captured output
AI_SOURCE_TYPES = frozenset({
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    "http://cv.iptc.org/newscodes/digitalsourcetype/"
    "compositeWithTrainedAlgorithmicMedia",
})

LISTS = ("success", "informational", "failure")

# --- code table: code -> (field, effect) ---
INTEGRITY, SIGNATURE, TIMESTAMP, TRUST, BOTH, NOTE = (
    "integrity", "signature", "timestamp", "trust", "both", "note")

BINDING_MATCH = "binding_match"  # integrity evidence
EVIDENCE = "evidence"  # recorded, supports a field but not sufficient alone
INVALID = "invalid"
NOT_CHECKED = "not_checked"
RECORDED = "recorded"  # recognized, no field effect
TS_OK = "ts_ok"
TS_IGNORED = "ts_ignored"
TRUSTED, UNTRUSTED = "trusted", "untrusted"

CODES: Dict[str, Tuple[str, str]] = {
    # integrity
    "assertion.dataHash.match": (INTEGRITY, BINDING_MATCH),
    "assertion.boxesHash.match": (INTEGRITY, BINDING_MATCH),
    "assertion.bmffHash.match": (INTEGRITY, BINDING_MATCH),
    "assertion.hashedURI.match": (INTEGRITY, EVIDENCE),
    "assertion.dataHash.mismatch": (INTEGRITY, INVALID),
    "assertion.boxesHash.mismatch": (INTEGRITY, INVALID),
    "assertion.bmffHash.mismatch": (INTEGRITY, INVALID),
    "assertion.hashedURI.mismatch": (INTEGRITY, INVALID),
    "assertion.missing": (INTEGRITY, INVALID),
    "claim.hardBindings.missing": (INTEGRITY, INVALID),
    "assertion.action.ingredientMismatch": (INTEGRITY, INVALID),
    "ingredient.manifest.validated": (INTEGRITY, EVIDENCE),
    "ingredient.manifest.mismatch": (INTEGRITY, INVALID),
    "ingredient.manifest.missing": (INTEGRITY, INVALID),
    "ingredient.unknownProvenance": (NOTE, RECORDED),
    # signature (trust codes excluded)
    "claimSignature.validated": (SIGNATURE, EVIDENCE),
    "claimSignature.insideValidity": (SIGNATURE, EVIDENCE),
    "claimSignature.mismatch": (SIGNATURE, INVALID),
    "claimSignature.missing": (SIGNATURE, INVALID),
    "claimSignature.outsideValidity": (SIGNATURE, INVALID),
    "signingCredential.invalid": (SIGNATURE, INVALID),
    "signingCredential.expired": (SIGNATURE, INVALID),
    "signingCredential.revoked": (SIGNATURE, INVALID),
    "signingCredential.ocsp.revoked": (SIGNATURE, INVALID),
    "signingCredential.ocsp.skipped": (SIGNATURE, RECORDED),
    "signingCredential.ocsp.notRevoked": (SIGNATURE, RECORDED),
    "signingCredential.ocsp.inaccessible": (SIGNATURE, RECORDED),
    "ingredient.claimSignature.validated": (SIGNATURE, EVIDENCE),
    "ingredient.claimSignature.mismatch": (SIGNATURE, INVALID),
    # trust: diagnostic only (sdk_trust_observation)
    "signingCredential.trusted": (TRUST, TRUSTED),
    "signingCredential.untrusted": (TRUST, UNTRUSTED),
    # timestamp (§14.8)
    "timeStamp.trusted": (TIMESTAMP, TS_OK),
    "timeStamp.validated": (TIMESTAMP, TS_OK),
    "timeStamp.malformed": (TIMESTAMP, TS_IGNORED),
    "timeStamp.mismatch": (TIMESTAMP, TS_IGNORED),
    "timeStamp.untrusted": (TIMESTAMP, TS_IGNORED),
    "timeStamp.outsideValidity": (TIMESTAMP, TS_IGNORED),
    # structural problems: neither integrity nor signature can be established
    "general.error": (BOTH, NOT_CHECKED),
    "algorithm.unsupported": (BOTH, NOT_CHECKED),
    "claim.missing": (BOTH, NOT_CHECKED),
    "claim.multiple": (BOTH, NOT_CHECKED),
    "manifest.missing": (BOTH, NOT_CHECKED),
    "manifest.inaccessible": (BOTH, NOT_CHECKED),
    "manifest.multipleParents": (BOTH, NOT_CHECKED),
    "assertion.cbor.invalid": (BOTH, NOT_CHECKED),
}

_URL = re.compile(r"^self#jumbf=/c2pa/([^/]+)(?:/(.*))?$")


class MappingError(ValueError):
    """The store cannot be mapped (e.g. no resolvable active manifest)."""


class TrustPolicy:
    """Decides signer_trust from the SDK trust observation."""

    name = "abstract"

    def signer_trust(self, sdk_trust_observation: List[str]) -> str:
        raise NotImplementedError


class _ProductionPolicy(TrustPolicy):
    """R1 production policy: the packaged anchor list is empty, so trust is
    always unknown, whatever the SDK reports."""

    name = "production"

    def signer_trust(self, sdk_trust_observation: List[str]) -> str:
        return "unknown"


PRODUCTION_POLICY = _ProductionPolicy()


@dataclass
class ManifestRecord:
    manifest_label: str
    is_active: bool
    relationship: Optional[str] = None
    title: Optional[str] = None
    integrity: str = "not_checked"
    signature: str = "not_checked"
    timestamp: str = "absent"
    signing_time_basis: str = "unknown"
    signer_trust: str = "unknown"
    declared_ai_use: str = "not_declared"
    sdk_trust_observation: List[str] = field(default_factory=list)
    sources: Dict[str, List[str]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


@dataclass
class MappedStore:
    validation_state: Optional[str]
    active_label: str
    policy: str
    records: List[ManifestRecord]  # active first, then ingredients
    unattributed: List[Dict[str, Any]]
    unmapped_status_codes: List[Dict[str, Any]] = field(default_factory=list)
    status_entries: List[Dict[str, Any]] = field(default_factory=list)
    ingredient_labels: List[str] = field(default_factory=list)
    mapping_version: str = MAPPING_VERSION

    @property
    def active(self) -> ManifestRecord:
        return self.records[0]

    @property
    def ingredients(self) -> List[ManifestRecord]:
        return [r for r in self.records[1:]
                if r.manifest_label in self.ingredient_labels]


def _entries(results: Optional[dict], default_label: Optional[str], origin: str):
    """(entry, list, label-or-None, origin) for every status entry."""
    for lst in LISTS:
        for entry in (results or {}).get(lst, []) or []:
            url = entry.get("url")
            label = None
            if isinstance(url, str):
                m = _URL.match(url)
                if m:
                    label = m.group(1)
                elif url.startswith("self#jumbf=") and "/c2pa/" not in url:
                    label = default_label  # relative: the list's own manifest
            yield entry, lst, label, origin


def _declared(manifest: dict) -> Tuple[str, List[str], List[str]]:
    found, other = [], []
    for assertion in manifest.get("assertions", []) or []:
        if assertion.get("label") not in ("c2pa.actions", "c2pa.actions.v2"):
            continue
        for action in (assertion.get("data") or {}).get("actions", []) or []:
            dst = action.get("digitalSourceType")
            if dst in AI_SOURCE_TYPES:
                found.append(f"{assertion.get('label')}: {dst}")
            elif dst is not None:
                other.append(f"digitalSourceType not accepted as AI use: {dst}")
    return ("declared" if found else "not_declared"), found, other


def _apply(record: ManifestRecord, codes: List[Tuple[str, str]], policy: TrustPolicy):
    """Set fields from (code, list) pairs attributed to this record."""
    integ = {"binding": [], "invalid": [], "not_checked": [], "evidence": []}
    sig = {"evidence": set(), "invalid": [], "not_checked": []}
    ts_ok, ts_ignored, ts_unknown = set(), [], []
    trust = []
    sources = {k: [] for k in ("integrity", "signature", "timestamp",
                               "sdk_trust_observation", "recorded")}

    for code, lst in codes:
        tag = f"{code} ({lst})"
        fld, effect = CODES.get(code, (None, None))
        if fld is None:
            record.notes.append(f"unrecognized status code {code} ({lst})")
            if isinstance(code, str) and code.startswith("timeStamp."):
                ts_unknown.append(code)
                sources["timestamp"].append(tag)
            integ["not_checked"].append(code)
            sig["not_checked"].append(code)
            sources["integrity"].append(tag)
            sources["signature"].append(tag)
            continue
        if effect in (BINDING_MATCH, EVIDENCE, TS_OK, TRUSTED) and lst != "success":
            # A positive-looking code outside success is not positive evidence.
            sources["recorded"].append(tag)
            continue
        if fld == INTEGRITY:
            sources["integrity"].append(tag)
            key = {BINDING_MATCH: "binding", INVALID: "invalid",
                   EVIDENCE: "evidence"}[effect]
            integ[key].append(code)
        elif fld == SIGNATURE:
            sources["signature"].append(tag)
            if effect == INVALID:
                sig["invalid"].append(code)
            elif effect == EVIDENCE:
                sig["evidence"].add(code)
        elif fld == TIMESTAMP:
            sources["timestamp"].append(tag)
            (ts_ok.add(code) if effect == TS_OK else ts_ignored.append(code))
        elif fld == TRUST:
            trust.append(code)
            sources["sdk_trust_observation"].append(tag)
        elif fld == BOTH:
            integ["not_checked"].append(code)
            sig["not_checked"].append(code)
            sources["integrity"].append(tag)
            sources["signature"].append(tag)
        else:
            sources["recorded"].append(tag)

    if integ["invalid"]:
        record.integrity = "invalid"
    elif integ["not_checked"]:
        record.integrity = "not_checked"
    elif record.is_active and integ["binding"]:
        record.integrity = "valid"
    else:
        record.integrity = "not_checked"
        if not record.is_active:
            record.notes.append("integrity of an ingredient manifest is not "
                                "checked: its content binding refers to "
                                "another asset")

    if sig["invalid"]:
        record.signature = "invalid"
    elif sig["not_checked"]:
        record.signature = "not_checked"
    elif {"claimSignature.validated",
          "claimSignature.insideValidity"} <= sig["evidence"]:
        record.signature = "valid"
    else:
        record.signature = "not_checked"

    if ts_unknown:
        record.timestamp = "not_checked"
    elif ts_ignored:
        record.timestamp = "ignored"
        record.notes += [f"time stamp ignored ({c}); separate from claim "
                         "signature validation (Litmus policy)"
                         for c in ts_ignored]
    elif ts_ok == {"timeStamp.trusted", "timeStamp.validated"}:
        record.timestamp = "trusted_validated"
    elif ts_ok:
        record.timestamp = "not_checked"
        record.notes.append("incomplete time-stamp codes: " + ", ".join(sorted(ts_ok)))
    else:
        record.timestamp = "absent"

    validity = {"claimSignature.insideValidity", "claimSignature.outsideValidity"}
    if record.timestamp == "trusted_validated":
        record.signing_time_basis = "trusted_timestamp"
    elif record.timestamp in ("ignored", "absent") and (
            validity & (sig["evidence"] | set(sig["invalid"]))):
        record.signing_time_basis = "current_time_check"
    else:
        record.signing_time_basis = "unknown"

    record.sdk_trust_observation = sorted(set(trust))
    record.signer_trust = policy.signer_trust(record.sdk_trust_observation)
    record.sources = {k: v for k, v in sources.items() if v}


def map_store(store: dict, policy: TrustPolicy = PRODUCTION_POLICY) -> MappedStore:
    """Map one manifest store (parsed ``Reader.json()``) to records."""
    if not isinstance(policy, TrustPolicy):
        raise TypeError("policy must be a TrustPolicy")
    manifests = store.get("manifests") or {}
    active_label = store.get("active_manifest")
    if not active_label or active_label not in manifests:
        raise MappingError("no resolvable active manifest in the store")

    # Ingredient manifests referenced by the active manifest, in order
    links = {}
    for ing in manifests[active_label].get("ingredients", []) or []:
        label = ing.get("active_manifest")
        if label:
            links[label] = ing
    order = [active_label] + [lb for lb in links if lb in manifests]
    order += [lb for lb in manifests if lb not in order]

    records = {}
    for label in order:
        ing = links.get(label, {})
        records[label] = ManifestRecord(
            manifest_label=label, is_active=label == active_label,
            relationship=ing.get("relationship"), title=ing.get("title"))
        if label != active_label and label not in links:
            records[label].notes.append("manifest not referenced by an "
                                        "ingredient of the active manifest")

    # Collect status entries with their attribution
    codes: Dict[str, List[Tuple[str, str]]] = {label: [] for label in order}
    unattributed = []
    results = store.get("validation_results") or {}
    entries = list(_entries(results.get("activeManifest"), active_label,
                            "validation_results.activeManifest"))
    delta_trust: Dict[str, List[Tuple[str, str]]] = {}
    for i, delta in enumerate(results.get("ingredientDeltas", []) or []):
        entries += list(_entries(delta.get("validationDeltas"), None,
                                 f"validation_results.ingredientDeltas[{i}]"))
    stored = []
    for label, ing in links.items():
        stored += list(_entries((ing.get("validation_results") or {})
                                .get("activeManifest"), label,
                                f"ingredient[{label}].validation_results"))

    # Current deltas supersede an ingredient's stored trust codes
    for entry, lst, label, origin in entries:
        code = entry.get("code")
        if label in codes:
            if origin.startswith("validation_results.ingredientDeltas") and \
                    CODES.get(code, (None,))[0] == TRUST:
                delta_trust.setdefault(label, []).append((code, lst))
            else:
                codes[label].append((code, lst))
        else:
            unattributed.append({"code": code, "list": lst, "url": entry.get("url"),
                                 "origin": origin})
    for entry, lst, label, origin in stored:
        code = entry.get("code")
        if label not in codes:
            unattributed.append({"code": code, "list": lst, "url": entry.get("url"),
                                 "origin": origin})
            continue
        if CODES.get(code, (None,))[0] == TRUST and label in delta_trust:
            continue
        codes[label].append((code, lst))
    for label, pairs in delta_trust.items():
        codes[label] += pairs

    for label in order:
        record = records[label]
        _apply(record, codes[label], policy)
        record.declared_ai_use, found, other = _declared(manifests[label])
        record.notes += other
        if found:
            record.sources["declared_ai_use"] = found

    active = records[active_label]
    if unattributed:
        for item in unattributed:
            active.notes.append(f"status code {item['code']} ({item['list']}) "
                                f"could not be attributed to a manifest "
                                f"(url {item['url']!r}); integrity and signature "
                                "not checked")
        if active.integrity != "invalid":
            active.integrity = "not_checked"
        if active.signature != "invalid":
            active.signature = "not_checked"

    return MappedStore(validation_state=store.get("validation_state"),
                       active_label=active_label, policy=policy.name,
                       records=[records[label] for label in order],
                       unattributed=unattributed,
                       ingredient_labels=[lb for lb in links if lb in manifests
                                          and lb != active_label],
                       status_entries=[
                           {"entry": dict(e), "list": lst, "label": lb,
                            "origin": origin}
                           for e, lst, lb, origin in entries + stored],
                       unmapped_status_codes=[
                           {"code": e.get("code"), "list": lst, "label": lb,
                            "url": e.get("url"), "origin": origin}
                           for e, lst, lb, origin in entries + stored
                           if e.get("code") not in CODES])
