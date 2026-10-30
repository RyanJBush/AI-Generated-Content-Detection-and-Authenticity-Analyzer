"""R1-D1: C2PA feasibility (docs/plans/R1-D-PLAN.md §f, §g, §h, §j, §p).

Production C2PA analysis stays disabled. These tests cover the packaged
production trust list, the settings builder, the committed fixtures, the
captured library output, the loopback trap with its positive control, and
test-anchor effect observations. Trust results here are SDK observations for
these fixtures and settings, not policy claims (§p Correction 4).
"""
import hashlib
import importlib.resources
import io
import json
import pathlib
import subprocess
import sys

import c2pa
import pytest

from litmus.c2pa import settings as settings_mod
from litmus.c2pa import trust_list as trust_mod
from litmus.c2pa.settings import (
    OFFLINE,
    TrustConfigError,
    build_settings,
    production_config,
    test_anchor_config,
)
from litmus.c2pa.trust_list import (
    TrustListError,
    load_production_trust_list,
    parse_trust_list,
)
from litmus.cli import main

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "c2pa"
OUTPUTS = ROOT / "eval" / "results" / "r1d1_library_outputs"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
TEST_ANCHOR = (FIXTURES / "pki" / "test_root_ca.pem").read_text(encoding="utf-8")
MIME = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def read(name, config):
    """(store dict, None) or (None, exception) for one fixture read."""
    settings = build_settings(config)
    context = c2pa.Context(settings=settings)
    try:
        with c2pa.Reader(MIME[pathlib.Path(name).suffix],
                         io.BytesIO((FIXTURES / name).read_bytes()),
                         context=context) as reader:
            return json.loads(reader.json()), None
    except c2pa.C2paError as e:
        return None, e
    finally:
        context.close()
        settings.close()


def codes(store, lst):
    return sorted({e["code"] for e in
                   store["validation_results"]["activeManifest"].get(lst, [])})


# --- production trust list (Step 2) ---

def test_production_trust_list_is_empty_and_versioned():
    trust = load_production_trust_list()
    assert trust.anchors == ()
    assert (trust.name, trust.version, trust.date) == (
        "production_trust_anchors", 1, "2026-10-30")
    assert trust.license == "OPEN \u2014 pending Ryan's decision"
    data = trust_mod.resource_bytes("production_trust_anchors")
    assert trust.sha256 == hashlib.sha256(data).hexdigest()
    assert b"BEGIN CERTIFICATE" not in data


def test_production_trust_list_loads_through_importlib_resources(monkeypatch):
    calls = []
    real = importlib.resources.files

    def spy(package):
        calls.append(package)
        return real(package)

    monkeypatch.setattr(trust_mod.importlib.resources, "files", spy)
    load_production_trust_list()
    assert calls == ["litmus.c2pa"]


def test_trust_list_parser_counts_pem_blocks_and_rejects_other_content():
    data = trust_mod.resource_bytes("production_trust_anchors")
    two = data + (TEST_ANCHOR * 2).encode()
    assert len(parse_trust_list(two, "production_trust_anchors").anchors) == 2
    with pytest.raises(TrustListError, match="other than PEM"):
        parse_trust_list(data + b"junk\n", "production_trust_anchors")
    with pytest.raises(TrustListError, match="carriage return"):
        parse_trust_list(data.replace(b"\n", b"\r\n"), "production_trust_anchors")
    with pytest.raises(TrustListError, match="header name"):
        parse_trust_list(data, "other")


# --- settings builder (Step 2; contents only, not evidence of effect) ---

def test_production_config_contents():
    assert production_config() == {
        "verify": {"remote_manifest_fetch": False, "ocsp_fetch": False,
                   "verify_trust": True},
        "core": {"allowed_network_hosts": [], "decode_identity_assertions": False},
    }


def test_test_anchor_config_contents():
    config = test_anchor_config([TEST_ANCHOR])
    assert config["trust"] == {"trust_anchors": TEST_ANCHOR}
    assert {k: v for k, v in config.items() if k != "trust"} == production_config()


def test_builder_does_not_mutate_the_offline_template():
    config = production_config()
    config["core"]["allowed_network_hosts"].append("x")
    assert OFFLINE["core"]["allowed_network_hosts"] == []
    assert production_config()["core"]["allowed_network_hosts"] == []


def test_production_config_never_references_test_material():
    text = json.dumps(production_config())
    assert "trust" not in production_config()
    for needle in ("tests", "fixtures", "BEGIN CERTIFICATE",
                   hashlib.sha256(TEST_ANCHOR.encode()).hexdigest()):
        assert needle not in text


def test_src_never_references_test_fixture_paths():
    for path in (ROOT / "src" / "litmus").rglob("*"):
        if path.is_file() and path.suffix in (".py", ".pem", ".txt", ".toml"):
            text = path.read_text(encoding="utf-8")
            for needle in ("tests/fixtures", "tests\\fixtures", "test_root_ca"):
                assert needle not in text, (path, needle)


def test_anchors_rejected_outside_the_explicit_test_path():
    with pytest.raises(TrustConfigError, match="explicit test path"):
        settings_mod._build([TEST_ANCHOR], test_path=False)
    with pytest.raises(TrustConfigError, match="at least one anchor"):
        test_anchor_config([])


def test_non_empty_production_list_is_refused(monkeypatch):
    real = trust_mod.resource_bytes(trust_mod.PRODUCTION_NAME)
    monkeypatch.setattr(trust_mod, "resource_bytes",
                        lambda name: real + TEST_ANCHOR.encode())
    with pytest.raises(TrustConfigError, match="must be empty"):
        production_config()


def test_configs_are_accepted_by_the_installed_library():
    # Acceptance only: the library also accepts unknown keys silently (R0)
    for config in (production_config(), test_anchor_config([TEST_ANCHOR])):
        settings = build_settings(config)
        context = c2pa.Context(settings=settings)
        context.close()
        settings.close()


# --- C2PA stays disabled in reports (Step 2) ---

@pytest.mark.parametrize("name", ["image.jpg", "image.png", "image.webp"])
def test_cli_image_report_unchanged(capsys, name):
    assert main(["analyze", str(ROOT / "tests" / "fixtures" / "inputs" / name)]) == 0
    out = capsys.readouterr().out
    golden = (ROOT / "tests" / "golden" / (name.replace(".", "_") + ".json"))
    assert out.encode("utf-8") == golden.read_bytes().replace(b"\r\n", b"\n")
    (origin,) = json.loads(out)["segments"][0]["origin"]
    assert origin["method_id"] == "image_origin_placeholder"
    assert "c2pa_analyzer_disabled_in_r0" in origin["reasons"]


def test_cli_analysis_does_not_import_c2pa():
    script = ("import sys\nfrom litmus.cli import main\n"
              f"main(['analyze', {str(FIXTURES / 'trusted_signer.jpg')!r}])\n"
              "bad = sorted(m for m in sys.modules if m == 'c2pa' or "
              "m.startswith('c2pa.') or m.startswith('litmus.c2pa'))\n"
              "print(bad, file=sys.stderr)\nsys.exit(1 if bad else 0)\n")
    proc = subprocess.run([sys.executable, "-I", "-c", script],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr.strip() == "[]"


# --- fixtures (Step 3) ---

def test_fixture_files_match_manifest():
    for name, meta in MANIFEST["fixtures"].items():
        data = (FIXTURES / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], name
        assert len(data) == meta["bytes"]
    for name, sha in MANIFEST["pki"]["files"].items():
        assert hashlib.sha256((FIXTURES / "pki" / name).read_bytes()
                              ).hexdigest() == sha, name
    assert MANIFEST["pki"]["tsa"] is None


# --- captured library output is current (Step 4) ---

def test_captured_library_outputs_are_current():
    index = json.loads((OUTPUTS / "index.json").read_text(encoding="utf-8"))
    configs = {"production": production_config(),
               "test_anchors": test_anchor_config([TEST_ANCHOR])}
    assert index["reads"]
    for key, entry in index["reads"].items():
        name, cfg = key.split(" / ")
        saved = json.loads((OUTPUTS / entry["file"]).read_text(encoding="utf-8"))
        store, exc = read(name, configs[cfg])
        if exc is not None:
            assert saved["outcome"] == "exception"
            assert (type(exc).__name__, str(exc)) == (saved["exception_class"],
                                                     saved["message"])
        else:
            assert saved["outcome"] == "read"
            assert store == saved["manifest_store"], key


# --- offline evidence (Step 5; Addendum B4) ---

REMOTE = "remote_reference.jpg"


def test_remote_reference_zero_connections_with_production_settings(
        c2pa_fixture_trap):
    store, exc = read(REMOTE, production_config())
    assert store is None
    assert "must fetch remote manifests" in str(exc)
    assert MANIFEST["trap"]["remote_url"] in str(exc)
    assert c2pa_fixture_trap.connections == []


def test_remote_reference_positive_control_reaches_trap(c2pa_fixture_trap):
    config = production_config()
    config["verify"]["remote_manifest_fetch"] = True
    config["core"]["allowed_network_hosts"] = [
        f"{c2pa_fixture_trap.host}:{c2pa_fixture_trap.port}"]
    store, exc = read(REMOTE, config)
    assert store is None and "404" in str(exc)
    assert len(c2pa_fixture_trap.connections) >= 1
    assert c2pa_fixture_trap.requests == ["/manifest.c2pa"]


# --- test-anchor effect checks (Step 6; SDK observations) ---

def test_trusted_fixture_with_test_anchor_reports_trusted():
    store, _ = read("trusted_signer.jpg", test_anchor_config([TEST_ANCHOR]))
    assert store["validation_state"] == "Trusted"
    assert "signingCredential.trusted" in codes(store, "success")
    assert "signingCredential.untrusted" not in codes(store, "failure")


def test_trusted_fixture_under_production_settings_reports_untrusted():
    store, _ = read("trusted_signer.jpg", production_config())
    assert store["validation_state"] == "Valid"
    assert codes(store, "failure") == ["signingCredential.untrusted"]
    assert "signingCredential.trusted" not in codes(store, "success")


def test_untrusted_fixture_with_test_anchor_reports_untrusted():
    store, _ = read("untrusted_signer.jpg", test_anchor_config([TEST_ANCHOR]))
    assert store["validation_state"] == "Valid"
    assert codes(store, "failure") == ["signingCredential.untrusted"]


def test_settings_set_trust_anchors_had_no_observed_effect():
    # SDK observation (R1-D1): the same anchor through Settings.set did not
    # change the trust status; the settings builder therefore uses from_dict
    settings = build_settings(production_config())
    settings.set("trust.trust_anchors", json.dumps(TEST_ANCHOR))
    context = c2pa.Context(settings=settings)
    try:
        with c2pa.Reader("image/jpeg", io.BytesIO(
                (FIXTURES / "trusted_signer.jpg").read_bytes()),
                context=context) as reader:
            store = json.loads(reader.json())
    finally:
        context.close()
        settings.close()
    assert "signingCredential.untrusted" in codes(store, "failure")
