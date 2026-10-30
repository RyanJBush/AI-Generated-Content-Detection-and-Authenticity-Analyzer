"""D2 mapping/rules: real captures plus explicitly constructed mutations."""
import importlib.util
import json
import pathlib

import pytest

from litmus.c2pa.mapping import (
    AI_SOURCE_TYPES,
    CODES,
    MappingError,
    TrustPolicy,
    map_store,
)
from litmus.c2pa.pipeline import analyze_c2pa
from litmus.c2pa.rules import RuleInput, evaluate_rules
from litmus.c2pa.settings import production_config, test_anchor_config

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/c2pa"
CAPTURES = ROOT / "eval/results/r1d1_library_outputs"


class TestOnlyPolicy(TrustPolicy):
    """Explicit test policy; never imported by package code."""

    __test__ = False
    name = "TEST ONLY: locally generated anchor"

    def signer_trust(self, observations):
        if "signingCredential.untrusted" in observations:
            return "untrusted"
        if "signingCredential.trusted" in observations:
            return "trusted"
        return "unknown"


def captured(name="trusted_signer", config="production"):
    path = CAPTURES / f"{name}_jpg__{config}.json"
    return json.loads(path.read_text(encoding="utf-8"))["manifest_store"]


def lists(store):
    return store["validation_results"]["activeManifest"]


def entry(store, code, label=None):
    return {"code": code,
            "url": f"self#jumbf=/c2pa/{label or store['active_manifest']}/"
                   "c2pa.signature"}


def result(store, policy=None):
    mapped = map_store(store) if policy is None else map_store(store, policy)
    return evaluate_rules(RuleInput(True, "store", mapped=mapped))


@pytest.mark.parametrize("code", ["assertion.future", "timeStamp.future",
                                 "signingCredential.future", "future.code"])
def test_unmapped_code_gives_validation_incomplete(code):
    store = captured("active_ai_declared")
    lists(store)["informational"].append(entry(store, code))
    mapped = map_store(store)
    assert (mapped.active.integrity, mapped.active.signature) == (
        "not_checked", "not_checked")
    assert result(store).rule == 6


@pytest.mark.parametrize("code", ["assertion.dataHash.match",
                                 "claimSignature.validated",
                                 "claimSignature.insideValidity"])
@pytest.mark.parametrize("destination", [None, "informational", "failure"])
def test_positive_evidence_required_in_success(code, destination):
    store = captured()
    removed = [e for e in lists(store)["success"] if e["code"] == code]
    lists(store)["success"] = [e for e in lists(store)["success"]
                              if e["code"] != code]
    if destination:
        lists(store)[destination] += removed
    assert result(store).rule == 6


def test_stored_ingredient_unknown_url_is_unattributed():
    store = captured("ingredient_ai_only")
    ing = store["manifests"][store["active_manifest"]]["ingredients"][0]
    ing["validation_results"]["activeManifest"]["failure"].append(
        entry(store, "claimSignature.mismatch", "unknown-label"))
    mapped = map_store(store)
    assert mapped.unattributed[0]["code"] == "claimSignature.mismatch"
    assert result(store).rule == 6


@pytest.mark.parametrize("label", ["c2pa.actions", "c2pa.actions.v2",
                                   "c2pa.actions.fake", "c2pa.actionsExtra"])
@pytest.mark.parametrize("uri", sorted(AI_SOURCE_TYPES) + [
    "trainedAlgorithmicMedia",
    "https://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    next(iter(sorted(AI_SOURCE_TYPES))) + "/"])
def test_declared_ai_use_exact_uris_and_assertions(label, uri):
    store = captured()
    store["manifests"][store["active_manifest"]]["assertions"] = [
        {"label": label, "data": {"actions": [{"digitalSourceType": uri}]}}]
    declared = label in {"c2pa.actions", "c2pa.actions.v2"} and uri in AI_SOURCE_TYPES
    assert map_store(store).active.declared_ai_use == (
        "declared" if declared else "not_declared")


def test_settings_rejection_gives_error():
    config = production_config()
    config["verify"]["remote_manifest_fetch"] = "wrong-type"
    outcome = analyze_c2pa((FIX / "trusted_signer.jpg").read_bytes(),
                           "image/jpeg", config=config)
    assert outcome.rule == 2
    assert "c2pa_settings_rejected" in outcome.reasons


@pytest.mark.parametrize("name,rule", [
    ("no_manifest.jpg", 3), ("remote_reference.jpg", 4),
    ("tampered.jpg", 5), ("active_ai_declared.jpg", 8),
    ("ingredient_ai_only.jpg", 9), ("trusted_signer.jpg", 10)])
def test_real_fixture_rules(name, rule):
    outcome = analyze_c2pa((FIX / name).read_bytes(), "image/jpeg",
                           config=production_config())
    assert outcome.rule == rule


def test_rule_7_real_fixture_explicit_test_policy():
    anchor = (FIX / "pki/test_root_ca.pem").read_text(encoding="utf-8")
    outcome = analyze_c2pa((FIX / "active_ai_declared.jpg").read_bytes(),
                           "image/jpeg", config=test_anchor_config([anchor]),
                           policy=TestOnlyPolicy())
    assert (outcome.rule, outcome.result) == (7, "supports_ai")


@pytest.mark.parametrize("path", sorted(p for p in FIX.glob("*.*")
                                       if p.suffix in {".jpg", ".png", ".webp"}))
def test_production_config_never_supports_ai(path):
    mime = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    outcome = analyze_c2pa(path.read_bytes(), mime[path.suffix],
                           config=production_config())
    assert outcome.result != "supports_ai"
    if "mapped" in outcome.details:
        assert all(r.signer_trust == "unknown"
                   for r in outcome.details["mapped"].records)


def test_production_policy_ignores_even_sdk_trusted_observations():
    store = captured("active_ai_declared", "test_anchors")
    mapped = map_store(store)
    assert "signingCredential.trusted" in mapped.active.sdk_trust_observation
    assert mapped.active.signer_trust == "unknown"
    assert result(store).rule == 8


@pytest.mark.parametrize("integrity,signature,trust,active_ai,ingredient_ai,rule", [
    ("invalid", "valid", "unknown", True, False, 5),
    ("valid", "invalid", "trusted", True, False, 5),
    ("not_checked", "valid", "trusted", True, False, 6),
    ("invalid", "not_checked", "trusted", True, True, 5),
    ("valid", "valid", "trusted", True, True, 7),
    ("valid", "valid", "untrusted", True, True, 8),
    ("valid", "valid", "unknown", True, True, 8),
    ("valid", "valid", "unknown", False, True, 9),
    ("valid", "valid", "unknown", False, False, 10)])
def test_rule_order_constructed_records(integrity, signature, trust, active_ai,
                                       ingredient_ai, rule):
    mapped = map_store(captured("ingredient_ai_only"))
    active = mapped.active
    active.integrity, active.signature, active.signer_trust = (
        integrity, signature, trust)
    active.declared_ai_use = "declared" if active_ai else "not_declared"
    ing = mapped.ingredients[0]
    ing.declared_ai_use = "declared" if ingredient_ai else "not_declared"
    ing.integrity, ing.signature, ing.signer_trust = "invalid", "invalid", "trusted"
    outcome = evaluate_rules(RuleInput(True, "store", mapped=mapped))
    assert outcome.rule == rule
    if rule == 9:
        assert outcome.details["declaring_ingredients"][0]["signature"] == "invalid"


def test_rule_1_precedes_2_and_does_not_read():
    def forbidden(*args):
        pytest.fail("unsupported formats must not reach read")
    assert analyze_c2pa(b"", "unsupported", config={}, read=forbidden,
                        supported=[]).rule == 1


def test_rule_2_precedes_3():
    assert evaluate_rules(RuleInput(True, "error", ["read_failed"])).rule == 2


@pytest.mark.parametrize("rule,expected", [
    (1, ("not_supported", "c2pa_format_unsupported")),
    (2, ("error", "c2pa_error")),
    (3, ("inconclusive", "no_credentials")),
    (4, ("inconclusive", "remote_reference_only")),
    (5, ("inconclusive", "validation_failed")),
    (6, ("inconclusive", "validation_incomplete")),
    (7, ("supports_ai", "trusted_provenance_ai_declared")),
    (8, ("inconclusive", "untrusted_signed_ai_declaration")),
    (9, ("inconclusive", "ingredient_ai_declaration")),
    (10, ("no_signal", "manifest_no_ai_declaration"))])
def test_all_ten_rule_results_and_labels(rule, expected):
    mapped = map_store(captured("ingredient_ai_only"))
    active = mapped.active
    active.declared_ai_use = "declared" if rule in (7, 8) else "not_declared"
    active.signer_trust = "trusted" if rule == 7 else "unknown"
    if rule == 5:
        active.signature = "invalid"
    if rule == 6:
        active.integrity = "not_checked"
    if rule == 10:
        mapped.ingredients[0].declared_ai_use = "not_declared"
    kind = {2: "error", 3: "no_credentials", 4: "remote_reference_only"}.get(
        rule, "store")
    outcome = evaluate_rules(RuleInput(rule != 1, kind, mapped=mapped))
    assert outcome.rule == rule
    assert (outcome.result, outcome.label) == expected
    assert outcome.reasons[0] == expected[1]


@pytest.mark.parametrize("owner", ["active", "ingredient"])
@pytest.mark.parametrize("origin", ["active", "stored_ingredient"])
def test_manifest_url_overrides_results_location(owner, origin):
    store = captured("ingredient_ai_only")
    active = store["manifests"][store["active_manifest"]]
    ingredient = active["ingredients"][0]
    label = store["active_manifest"] if owner == "active" else (
        ingredient["active_manifest"])
    target = lists(store) if origin == "active" else (
        ingredient["validation_results"]["activeManifest"])
    status = entry(store, "assertion.action.ingredientMismatch", label)
    target["failure"].append(status)
    mapped = map_store(store)
    assert mapped.active.integrity == ("invalid" if owner == "active" else "valid")
    assert mapped.ingredients[0].integrity == (
        "invalid" if owner == "ingredient" else "not_checked")
    assert any(e["entry"] == status and e["label"] == label
               for e in mapped.status_entries)


def test_relative_ingredient_url_and_current_trust_delta():
    store = captured("ingredient_ai_only", "test_anchors")
    ing = store["manifests"][store["active_manifest"]]["ingredients"][0]
    ing_results = ing["validation_results"]["activeManifest"]
    for bucket in ing_results.values():
        for status in bucket:
            status["url"] = "self#jumbf=c2pa.signature"
    mapped = map_store(store, TestOnlyPolicy())
    assert mapped.ingredients[0].signature == "valid"
    assert mapped.ingredients[0].signer_trust == "trusted"
    assert mapped.active.integrity == "valid"


def test_invalid_wins_over_unknown_codes():
    store = captured("tampered")
    lists(store)["failure"].append(entry(store, "future.code"))
    mapped = map_store(store)
    assert mapped.active.integrity == "invalid"
    assert mapped.active.signature == "not_checked"
    assert result(store).rule == 5


@pytest.mark.parametrize("path", sorted(p for p in
                                       (FIX / "constructed").glob("*.json")
                                       if p.name != "mapping_rows.json"))
def test_constructed_context_and_timestamp_cases(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["constructed"] is True
    mapped = map_store(record["manifest_store"])
    active = mapped.active
    name = path.stem
    if name.startswith("timestamp_ignored"):
        assert (active.timestamp, active.signature) == ("ignored", "valid")
        assert active.signing_time_basis == "current_time_check"
    elif name == "timestamp_trusted_validated":
        assert (active.timestamp, active.signature) == ("trusted_validated", "valid")
        assert active.signing_time_basis == "trusted_timestamp"
    elif name == "claim_signature_outside_validity":
        assert active.signature == "invalid"
    elif name == "integrity_invalid_with_timestamp":
        assert active.timestamp == "trusted_validated"
        assert result(record["manifest_store"]).rule == 5
    elif name == "active_ingredient_mismatch":
        assert active.integrity == "invalid"
    elif name == "ingredient_manifest_mismatch":
        assert active.integrity == "valid"
        assert mapped.ingredients[0].integrity == "invalid"
        assert result(record["manifest_store"]).rule == 9
    else:
        assert result(record["manifest_store"]).rule == 6


def test_inside_validity_never_proves_timestamp_and_overall_state_is_diagnostic():
    store = captured()
    store["validation_state"] = "Invalid"
    mapped = map_store(store)
    assert (mapped.active.signature, mapped.active.timestamp) == ("valid", "absent")
    assert mapped.active.signing_time_basis != "trusted_timestamp"
    assert result(store).rule == 10


def test_constructed_generator_matches_files():
    spec = importlib.util.spec_from_file_location(
        "constructed", ROOT / "scripts/make_c2pa_constructed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, expected in module.build().items():
        assert json.loads((FIX / "constructed" / name).read_text(
            encoding="utf-8")) == expected


def test_missing_active_manifest_is_mapping_error():
    with pytest.raises(MappingError):
        map_store({})


def test_no_validation_results_does_not_infer_validity():
    store = captured()
    del store["validation_results"]
    assert result(store).rule == 6


def test_unreferenced_manifest_does_not_trigger_ingredient_rule():
    store = captured("ingredient_ai_only")
    store["manifests"][store["active_manifest"]]["ingredients"] = []
    assert result(store).rule == 10


def test_near_miss_uri_recorded_without_becoming_declaration():
    store = captured("active_ai_declared")
    assertion = store["manifests"][store["active_manifest"]]["assertions"][0]
    uri = next(iter(sorted(AI_SOURCE_TYPES))) + "/"
    assertion["data"]["actions"][0]["digitalSourceType"] = uri
    active = map_store(store).active
    assert active.declared_ai_use == "not_declared"
    assert any(uri in note for note in active.notes)


@pytest.mark.parametrize("code", sorted(CODES))
def test_mapping_row_constructed(code):
    """Each code explicitly injected; this is not evidence of SDK emission."""
    fixture = json.loads((FIX / "constructed/mapping_rows.json").read_text(
        encoding="utf-8"))
    assert fixture["constructed"] is True
    assert set(fixture["cases"]) == set(CODES)
    store = fixture["cases"][code]
    mapped = map_store(store)
    active = mapped.active
    if code in INTEGRITY_INVALID:
        assert active.integrity == "invalid"
    elif code in SIGNATURE_INVALID:
        assert active.signature == "invalid"
    elif code in INCOMPLETE:
        assert (active.integrity, active.signature) == ("not_checked", "not_checked")
    elif code.startswith("timeStamp."):
        assert active.signature == "valid"
        assert active.timestamp == ("not_checked" if code in POSITIVE_CODES
                                    else "ignored")
    else:
        assert (active.integrity, active.signature) == ("valid", "valid")
    assert active.signer_trust == "unknown"


POSITIVE_CODES = set("""
assertion.dataHash.match assertion.boxesHash.match assertion.bmffHash.match
assertion.hashedURI.match claimSignature.validated claimSignature.insideValidity
ingredient.manifest.validated ingredient.claimSignature.validated
signingCredential.trusted timeStamp.trusted timeStamp.validated
""".split())
INTEGRITY_INVALID = set("""
assertion.dataHash.mismatch assertion.boxesHash.mismatch assertion.bmffHash.mismatch
assertion.hashedURI.mismatch assertion.missing claim.hardBindings.missing
assertion.action.ingredientMismatch ingredient.manifest.mismatch
ingredient.manifest.missing
""".split())
SIGNATURE_INVALID = set("""
claimSignature.mismatch claimSignature.missing claimSignature.outsideValidity
signingCredential.invalid signingCredential.expired signingCredential.revoked
signingCredential.ocsp.revoked ingredient.claimSignature.mismatch
""".split())
INCOMPLETE = set("""
general.error algorithm.unsupported claim.missing claim.multiple manifest.missing
manifest.inaccessible manifest.multipleParents assertion.cbor.invalid
""".split())
