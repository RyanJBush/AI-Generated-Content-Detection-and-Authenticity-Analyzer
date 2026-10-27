"""c2pa-python offline settings (Addendum A1.2, A1.4.3, A1.4.4, B4).

API used (installed c2pa-python 0.38.0, .venv/Lib/site-packages/c2pa/c2pa.py):
``Settings.set(path, value)`` (value is a JSON string), ``Context(settings=...)``
and ``Reader(format, stream, context=...)``. The deprecated thread-local
``load_settings`` is not used.
"""
import io

import c2pa
import pytest
from PIL import Image

# A1.2 settings, as (dot path, JSON value)
OFFLINE_SETTINGS = [
    ("verify.remote_manifest_fetch", "false"),
    ("verify.ocsp_fetch", "false"),
    ("core.allowed_network_hosts", "[]"),
    ("core.decode_identity_assertions", "false"),
]
# Wrong-type value per setting, with the type the library should demand
WRONG_TYPE = {
    "verify.remote_manifest_fetch": ('"x"', "expected a boolean"),
    "verify.ocsp_fetch": ('"x"', "expected a boolean"),
    "core.allowed_network_hosts": ('"x"', "expected a sequence"),
    "core.decode_identity_assertions": ('"x"', "expected a boolean"),
}
UNKNOWN_KEY = "verify.litmus_no_such_key"


def _settings(pairs):
    s = c2pa.Settings()
    for path, value in pairs:
        s.set(path, value)
    return s


# --- A1.4.4 settings presence ---

def test_c2pa_accepts_offline_settings():
    s = _settings(OFFLINE_SETTINGS)
    ctx = c2pa.Context(settings=s)
    assert ctx.is_valid
    ctx.close()
    s.close()


def test_c2pa_unknown_key_is_silently_accepted():
    """Records a library limitation: unknown keys are NOT rejected.

    A1.4.4 requires an unknown key to fail. With c2pa-python 0.38.0 it does
    not, so acceptance alone cannot show that a key exists. If a future
    version starts rejecting unknown keys this test fails and the presence
    claim should be re-evaluated.
    """
    _settings([(UNKNOWN_KEY, "false")]).close()
    _settings([(UNKNOWN_KEY, '"any type"')]).close()


@pytest.mark.parametrize("path", sorted(WRONG_TYPE))
def test_c2pa_offline_keys_are_type_checked(path):
    # A known key validates its value type; an unknown key does not (above).
    value, expected = WRONG_TYPE[path]
    with pytest.raises(c2pa.C2paError) as exc:
        _settings([(path, value)])
    message = str(exc.value)
    assert f"'{path}'" in message
    assert expected in message


# --- A1.4.3 remote-fetch trap and positive control (B4) ---

def _remote_reference_jpeg(url: str) -> bytes:
    """JPEG with no embedded manifest whose XMP dcterms:provenance names url."""
    xmp = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dcterms="http://purl.org/dc/terms/"'
        f' dcterms:provenance="{url}"/>'
        "</rdf:RDF></x:xmpmeta>"
    ).encode("utf-8")
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="JPEG", xmp=xmp)
    data = buf.getvalue()
    assert url.encode("ascii") in data
    return data


def _read(data: bytes, pairs):
    settings = _settings(pairs)
    ctx = c2pa.Context(settings=settings)
    try:
        with pytest.raises(c2pa.C2paError) as exc:
            c2pa.Reader("image/jpeg", io.BytesIO(data), context=ctx)
        return str(exc.value)
    finally:
        ctx.close()
        settings.close()


def test_c2pa_remote_reference_zero_connections_with_offline_settings(trap):
    url = trap.url + "/manifest.c2pa"
    message = _read(_remote_reference_jpeg(url), OFFLINE_SETTINGS)
    assert "must fetch remote manifests" in message
    assert url in message
    assert trap.connections == []


def test_c2pa_remote_reference_positive_control_reaches_trap(trap):
    url = trap.url + "/manifest.c2pa"
    control = [
        ("verify.remote_manifest_fetch", "true"),
        ("core.allowed_network_hosts", f'["{trap.host}:{trap.port}"]'),
    ]
    message = _read(_remote_reference_jpeg(url), control)
    assert "404" in message
    assert len(trap.connections) == 1
    assert trap.requests == ["/manifest.c2pa"]


def test_c2pa_empty_allowed_hosts_alone_blocks_fetch(trap):
    url = trap.url + "/manifest.c2pa"
    only_hosts = [
        ("verify.remote_manifest_fetch", "true"),
        ("core.allowed_network_hosts", "[]"),
    ]
    message = _read(_remote_reference_jpeg(url), only_hosts)
    assert "not permitted by the allowed list" in message
    assert trap.connections == []
