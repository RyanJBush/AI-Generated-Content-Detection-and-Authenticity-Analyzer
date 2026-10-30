"""Addendum A2 C2PA result rules (R1-D2; plan §d). Pure functions.

Rules are evaluated in order; the first matching rule determines ``result``
(Addendum A2; verbatim table in docs/plans/R1-D-PLAN.md §d). Conditions
concern the active manifest unless stated:

1. Format not supported by the pinned c2pa library
   -> not_supported / c2pa_format_unsupported
2. Library error or timeout -> error / c2pa_error
3. No manifest store found -> inconclusive / no_credentials
4. Only a remote manifest reference (not fetched, A1)
   -> inconclusive / remote_reference_only
5. integrity = invalid or signature = invalid
   -> inconclusive / validation_failed
6. integrity = not_checked or signature = not_checked
   -> inconclusive / validation_incomplete
7. declared_ai_use = declared and signer_trust = trusted
   -> supports_ai / trusted_provenance_ai_declared
8. declared_ai_use = declared and signer_trust in {untrusted, unknown}
   -> inconclusive / untrusted_signed_ai_declaration
9. Active not declared; >= 1 ingredient manifest declares AI use
   -> inconclusive / ingredient_ai_declaration
10. Active not declared; no ingredient declares AI use
    -> no_signal / manifest_no_ai_declaration
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from litmus.c2pa.mapping import MappedStore

EMPTY_TRUST_LIMITATION = (
    "With an empty production trust list, signer_trust is unknown for every "
    "manifest, so no C2PA result can be supports_ai in R1 under the production "
    "policy. A valid AI-use declaration alone yields inconclusive / "
    "untrusted_signed_ai_declaration.")
PROVENANCE_ONLY = ("R1 checks C2PA provenance only; it does not detect "
                   "AI-generated images.")
TIMEOUT_LIMITATION = ("A timed-out C2PA read is not cancelled; it keeps running "
                      "on the C2PA worker until it finishes.")

RULE_LABELS = {
    1: ("not_supported", "c2pa_format_unsupported"),
    2: ("error", "c2pa_error"),
    3: ("inconclusive", "no_credentials"),
    4: ("inconclusive", "remote_reference_only"),
    5: ("inconclusive", "validation_failed"),
    6: ("inconclusive", "validation_incomplete"),
    7: ("supports_ai", "trusted_provenance_ai_declared"),
    8: ("inconclusive", "untrusted_signed_ai_declaration"),
    9: ("inconclusive", "ingredient_ai_declaration"),
    10: ("no_signal", "manifest_no_ai_declaration"),
}
RULE_LIMITATIONS = {
    3: ["Absence of Content Credentials is not evidence of human origin."],
    4: ["The remote manifest was not fetched (offline)."],
    5: ["Declarations are shown but not used as evidence: the manifest failed "
        "validation."],
    6: ["Validation could not be completed for the active manifest."],
    9: ["Ingredient validation states are reported but never make a result "
        "supports_ai."],
    10: ["A manifest without an AI-use declaration is not evidence of human "
         "origin."],
}


@dataclass
class RuleInput:
    format_supported: bool
    read_kind: str  # store | no_credentials | remote_reference_only | error
    error_reasons: List[str] = field(default_factory=list)
    mapped: Optional[MappedStore] = None


@dataclass
class RuleOutcome:
    rule: int
    result: str
    label: str
    reasons: List[str]
    limitations: List[str]
    details: Dict[str, Any] = field(default_factory=dict)


def _which_rule(inp: RuleInput) -> int:
    if not inp.format_supported:
        return 1
    if inp.read_kind == "error":
        return 2
    if inp.read_kind == "no_credentials":
        return 3
    if inp.read_kind == "remote_reference_only":
        return 4
    if inp.read_kind != "store" or inp.mapped is None:
        return 2
    active = inp.mapped.active
    if "invalid" in (active.integrity, active.signature):
        return 5
    if "not_checked" in (active.integrity, active.signature):
        return 6
    if active.declared_ai_use == "declared":
        if active.signer_trust == "trusted":
            return 7
        return 8  # untrusted or unknown
    if any(r.declared_ai_use == "declared" for r in inp.mapped.ingredients):
        return 9
    return 10


def evaluate_rules(inp: RuleInput) -> RuleOutcome:
    rule = _which_rule(inp)
    result, label = RULE_LABELS[rule]
    reasons = [label]
    if rule == 2:
        reasons += inp.error_reasons
    limitations = [EMPTY_TRUST_LIMITATION, PROVENANCE_ONLY,
                   *RULE_LIMITATIONS.get(rule, [])]
    if "c2pa_timeout" in inp.error_reasons:
        limitations.append(TIMEOUT_LIMITATION)
    details: Dict[str, Any] = {}
    if rule == 9:
        details["declaring_ingredients"] = [{
            "manifest_label": r.manifest_label, "relationship": r.relationship,
            "title": r.title, "integrity": r.integrity, "signature": r.signature,
            "timestamp": r.timestamp, "signer_trust": r.signer_trust,
        } for r in inp.mapped.ingredients if r.declared_ai_use == "declared"]
    return RuleOutcome(rule, result, label, reasons, limitations, details)
