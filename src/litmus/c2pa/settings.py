"""C2PA settings builder (Addendum A1.2; R1-D plan §f, §h).

Builds the configuration dict for every C2PA read:

- the A1.2 offline settings: verify.remote_manifest_fetch = false,
  verify.ocsp_fetch = false, core.allowed_network_hosts = [],
  core.decode_identity_assertions = false;
- verify.verify_trust = true (trust verification stays on);
- trust anchors: none from the packaged production list (empty in R1), or
  test anchors passed explicitly through ``test_anchor_config`` (tests only).

The dict is applied with ``c2pa.Settings.from_dict`` (installed c2pa-python
0.38.0, ``c2pa/c2pa.py``: ``Settings.from_dict`` -> ``from_json`` ->
``update`` -> native ``c2pa_settings_update_from_string``), then attached
with ``c2pa.Context(settings=...)``.

The contents of this dict are not evidence of effect: the library silently
accepts unknown keys (R0). R1-D1 observed that ``Settings.set`` on
``trust.trust_anchors`` had no observable effect while ``from_dict`` did; see
docs/decisions.md (R1-D1). Offline effect is shown only by the trap test with
its positive control.
"""
import copy
from typing import Any, Dict, Sequence

from litmus.c2pa.trust_list import load_production_trust_list

OFFLINE = {
    "verify": {"remote_manifest_fetch": False, "ocsp_fetch": False},
    "core": {"allowed_network_hosts": [], "decode_identity_assertions": False},
}


class TrustConfigError(ValueError):
    pass


def _build(anchors_pem: Sequence[str], *, test_path: bool) -> Dict[str, Any]:
    if anchors_pem and not test_path:
        raise TrustConfigError("trust anchors may be passed only through the "
                               "explicit test path (test_anchor_config)")
    config = copy.deepcopy(OFFLINE)
    config["verify"]["verify_trust"] = True
    if anchors_pem:
        config["trust"] = {"trust_anchors": "".join(anchors_pem)}
    return config


def production_config() -> Dict[str, Any]:
    """Offline settings plus the packaged production trust list (empty in R1)."""
    trust = load_production_trust_list()
    if trust.anchors:
        raise TrustConfigError("R1 policy: the production trust list must be empty")
    return _build(trust.anchors, test_path=False)


def test_anchor_config(anchors_pem: Sequence[str]) -> Dict[str, Any]:
    """TEST PATH ONLY: offline settings plus explicitly passed test anchors."""
    if not anchors_pem:
        raise TrustConfigError("test_anchor_config needs at least one anchor")
    return _build(anchors_pem, test_path=True)


test_anchor_config.__test__ = False  # not a pytest test despite its name


def build_settings(config: Dict[str, Any]):
    """A new c2pa.Settings from a config dict (import deferred to call time)."""
    import c2pa

    return c2pa.Settings.from_dict(config)
