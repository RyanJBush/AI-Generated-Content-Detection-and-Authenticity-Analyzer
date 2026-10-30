"""R1-D1 C2PA fixture generator -> tests/fixtures/c2pa/ (docs/plans/R1-D-PLAN.md §j).

Builds a local TEST-ONLY certificate hierarchy with ``cryptography`` and signs
small Pillow images with the installed c2pa-python ``Builder``. Nothing is
downloaded and no timestamp authority is used (``ta_url=None``). All private
keys written here are TEST ONLY and must never be used for anything else.

Hierarchy (ECDSA P-256, signing algorithm ES256):

- test root CA -> test intermediate CA -> test signer   (the "trusted" chain;
  the test root is the anchor loaded by tests only)
- untrusted root CA -> untrusted signer                (separate root)

Validity: 2026-01-01T00:00:00Z to 2046-01-01T00:00:00Z for every certificate,
so the fixtures stay inside validity during the project (no TSA means the
library can only check validity against the current time).

Fixtures (the asset bytes; signatures and claim times vary per run, so a
regenerated set has new hashes and is a reviewed change):

- trusted_signer.{jpg,png,webp}  signed by the test signer, digitalCapture
- untrusted_signer.jpg           signed by the untrusted signer
- no_manifest.{jpg,png,webp}     plain Pillow images
- tampered.jpg                   trusted_signer.jpg with one byte changed
                                 after signing (in the entropy-coded data)
- active_ai_declared.jpg         active c2pa.actions with
                                 digitalSourceType trainedAlgorithmicMedia
- ingredient_ai_only.jpg         active manifest without an AI declaration;
                                 one componentOf ingredient whose own
                                 manifest declares trainedAlgorithmicMedia
- remote_reference.jpg           Builder.set_no_embed() + set_remote_url()
                                 pointing at the loopback trap address
                                 REMOTE_URL; the manifest store is written
                                 separately to remote_reference.c2pa

Each fixture's SHA-256 and generator parameters go to manifest.json.

    .venv\\Scripts\\python.exe scripts\\generate_c2pa_fixtures.py [--out DIR]
"""
import argparse
import datetime
import hashlib
import io
import json
import pathlib
import sys

import c2pa
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "tests" / "fixtures" / "c2pa"
NOT_BEFORE = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
NOT_AFTER = datetime.datetime(2046, 1, 1, tzinfo=datetime.timezone.utc)
TRAP_HOST = "127.0.0.1"
TRAP_PORT = 47811
REMOTE_URL = f"http://{TRAP_HOST}:{TRAP_PORT}/manifest.c2pa"
IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"
SIZE = (64, 48)
# The A1.2 offline settings, also applied while signing (no network), plus no
# thumbnails (keeps fixtures small). Applied with Settings.from_dict.
SIGNING_SETTINGS = {
    "verify": {"remote_manifest_fetch": False, "ocsp_fetch": False},
    "core": {"allowed_network_hosts": [], "decode_identity_assertions": False},
    "builder": {"thumbnail": {"enabled": False}},
}


def _name(common_name):
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME,
                                         "Litmus TEST ONLY"),
                      x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def make_cert(common_name, key, issuer_name, issuer_key, *, ca, path_length=None):
    """One certificate; CA or end-entity profile (fields listed in manifest)."""
    builder = (x509.CertificateBuilder()
               .subject_name(_name(common_name))
               .issuer_name(issuer_name)
               .public_key(key.public_key())
               .serial_number(x509.random_serial_number())
               .not_valid_before(NOT_BEFORE)
               .not_valid_after(NOT_AFTER)
               .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                   key.public_key()), critical=False)
               .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                   issuer_key.public_key()), critical=False))
    if ca:
        builder = (builder
                   .add_extension(x509.BasicConstraints(ca=True,
                                                        path_length=path_length),
                                  critical=True)
                   .add_extension(x509.KeyUsage(
                       digital_signature=False, content_commitment=False,
                       key_encipherment=False, data_encipherment=False,
                       key_agreement=False, key_cert_sign=True, crl_sign=True,
                       encipher_only=False, decipher_only=False), critical=True))
    else:
        builder = (builder
                   .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                                  critical=True)
                   .add_extension(x509.KeyUsage(
                       digital_signature=True, content_commitment=False,
                       key_encipherment=False, data_encipherment=False,
                       key_agreement=False, key_cert_sign=False, crl_sign=False,
                       encipher_only=False, decipher_only=False), critical=True)
                   .add_extension(x509.ExtendedKeyUsage(
                       [ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False))
    return builder.sign(issuer_key, hashes.SHA256())


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def key_pem(key):
    return key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def make_pki():
    new = lambda: ec.generate_private_key(ec.SECP256R1())  # noqa: E731
    root_key, int_key, signer_key = new(), new(), new()
    root = make_cert("Litmus TEST ONLY root CA", root_key, _name(
        "Litmus TEST ONLY root CA"), root_key, ca=True, path_length=1)
    inter = make_cert("Litmus TEST ONLY intermediate CA", int_key, root.subject,
                      root_key, ca=True, path_length=0)
    signer = make_cert("Litmus TEST ONLY signer", signer_key, inter.subject,
                       int_key, ca=False)
    u_root_key, u_signer_key = new(), new()
    u_root = make_cert("Litmus TEST ONLY untrusted root CA", u_root_key, _name(
        "Litmus TEST ONLY untrusted root CA"), u_root_key, ca=True, path_length=0)
    u_signer = make_cert("Litmus TEST ONLY untrusted signer", u_signer_key,
                         u_root.subject, u_root_key, ca=False)
    return {
        "test_root_ca.pem": pem(root),
        "test_intermediate_ca.pem": pem(inter),
        # Chain passed to the signer: end-entity first, then the intermediate
        "test_signer_chain.pem": pem(signer) + pem(inter),
        "test_signer_key.pem": key_pem(signer_key),
        "untrusted_root_ca.pem": pem(u_root),
        "untrusted_signer_chain.pem": pem(u_signer),
        "untrusted_signer_key.pem": key_pem(u_signer_key),
    }


def image_bytes(fmt):
    img = Image.new("RGB", SIZE)
    img.putdata([((x * 4) % 256, (y * 5) % 256, (x * y) % 256)
                 for y in range(SIZE[1]) for x in range(SIZE[0])])
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}


def manifest_def(title, ext, source_type, extra_actions=()):
    return {
        "claim_generator_info": [{"name": "litmus-test-fixtures", "version": "1"}],
        "title": title,
        "format": MIME[ext],
        "assertions": [{"label": "c2pa.actions", "data": {"actions": [
            {"action": "c2pa.created", "digitalSourceType": IPTC + source_type},
            *extra_actions]}}],
    }


def offline_context():
    settings = c2pa.Settings.from_dict(SIGNING_SETTINGS)
    return settings, c2pa.Context(settings=settings)


def sign(definition, ext, source, chain, key, *, ingredients=(), remote_url=None):
    """Sign source bytes; returns (asset bytes, manifest store bytes)."""
    info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.ES256, chain, key, None)
    signer = c2pa.Signer.from_info(info)
    settings, context = offline_context()
    try:
        builder = c2pa.Builder.from_json(json.dumps(definition), context)
        for ingredient_json, ingredient_bytes in ingredients:
            builder.add_ingredient(json.dumps(ingredient_json), MIME["jpg"],
                                   io.BytesIO(ingredient_bytes))
        if remote_url is not None:
            builder.set_no_embed()
            builder.set_remote_url(remote_url)
        dest = io.BytesIO()
        store = builder.sign(signer, MIME[ext], io.BytesIO(source), dest)
        return dest.getvalue(), store
    finally:
        context.close()
        settings.close()
        signer.close()


def tamper(data):
    """Change one byte inside the JPEG entropy-coded data (after SOS)."""
    sos = data.rindex(b"\xff\xda")
    pos = sos + (len(data) - sos) // 2
    while data[pos] == 0xFF or data[pos - 1] == 0xFF or data[pos] == 0x00:
        pos += 1
    return data[:pos] + bytes([data[pos] ^ 0x01]) + data[pos + 1:]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    out = args.out
    (out / "pki").mkdir(parents=True, exist_ok=True)

    pki = make_pki()
    for name, data in pki.items():
        (out / "pki" / name).write_bytes(data)
    chain, key = pki["test_signer_chain.pem"], pki["test_signer_key.pem"]
    u_chain, u_key = pki["untrusted_signer_chain.pem"], pki["untrusted_signer_key.pem"]

    fixtures, params = {}, {}
    for ext in ("jpg", "png", "webp"):
        plain = image_bytes(PIL_FORMAT[ext])
        fixtures[f"no_manifest.{ext}"] = plain
        params[f"no_manifest.{ext}"] = {"image": f"{SIZE[0]}x{SIZE[1]} gradient",
                                        "format": PIL_FORMAT[ext]}
        name = f"trusted_signer.{ext}"
        fixtures[name], _ = sign(manifest_def(name, ext, "digitalCapture"), ext,
                                 plain, chain, key)
        params[name] = {"signer": "test signer (test root -> intermediate)",
                        "digitalSourceType": "digitalCapture",
                        "source": f"no_manifest.{ext}"}

    jpg = fixtures["no_manifest.jpg"]
    fixtures["untrusted_signer.jpg"], _ = sign(
        manifest_def("untrusted_signer.jpg", "jpg", "digitalCapture"), "jpg", jpg,
        u_chain, u_key)
    params["untrusted_signer.jpg"] = {"signer": "untrusted signer (separate root)",
                                      "digitalSourceType": "digitalCapture",
                                      "source": "no_manifest.jpg"}

    fixtures["tampered.jpg"] = tamper(fixtures["trusted_signer.jpg"])
    params["tampered.jpg"] = {"source": "trusted_signer.jpg",
                              "change": "one byte XOR 0x01 in the entropy-coded "
                                        "data after the last SOS marker"}

    fixtures["active_ai_declared.jpg"], _ = sign(
        manifest_def("active_ai_declared.jpg", "jpg", "trainedAlgorithmicMedia"),
        "jpg", jpg, chain, key)
    params["active_ai_declared.jpg"] = {
        "signer": "test signer", "digitalSourceType": "trainedAlgorithmicMedia",
        "source": "no_manifest.jpg"}

    ingredient = {"title": "active_ai_declared.jpg", "relationship": "componentOf",
                  "label": "ai_ingredient"}
    placed = {"action": "c2pa.placed",
              "parameters": {"ingredientIds": ["ai_ingredient"]}}
    fixtures["ingredient_ai_only.jpg"], _ = sign(
        manifest_def("ingredient_ai_only.jpg", "jpg", "digitalCapture", [placed]),
        "jpg", jpg, chain, key,
        ingredients=[(ingredient, fixtures["active_ai_declared.jpg"])])
    params["ingredient_ai_only.jpg"] = {
        "signer": "test signer", "digitalSourceType": "digitalCapture (active)",
        "ingredient": {**ingredient, "source": "active_ai_declared.jpg"},
        "extra_action": placed, "source": "no_manifest.jpg"}

    fixtures["remote_reference.jpg"], store = sign(
        manifest_def("remote_reference.jpg", "jpg", "digitalCapture"), "jpg", jpg,
        chain, key, remote_url=REMOTE_URL)
    fixtures["remote_reference.c2pa"] = store
    params["remote_reference.jpg"] = {"signer": "test signer", "no_embed": True,
                                      "remote_url": REMOTE_URL,
                                      "source": "no_manifest.jpg"}
    params["remote_reference.c2pa"] = {"what": "manifest store returned by "
                                               "Builder.sign for remote_reference.jpg"}

    for name, data in fixtures.items():
        (out / name).write_bytes(data)

    record = {
        "checkpoint": "R1-D1",
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": " ".join([sys.executable] + sys.argv),
        "library": {"c2pa_python": "0.38.0 (dist-info)",
                    "sdk_version": c2pa.sdk_version()},
        "signing_settings": SIGNING_SETTINGS,
        "test_only": "All keys and certificates under pki/ are TEST ONLY: generated "
                     "locally for Litmus tests, never for production or trust.",
        "pki": {
            "algorithm": "ECDSA P-256, SHA-256 signatures; signing alg ES256",
            "validity": [NOT_BEFORE.isoformat(), NOT_AFTER.isoformat()],
            "ca_profile": "BasicConstraints CA=true (critical, pathLen root 1 / "
                          "intermediate 0 / untrusted root 0); KeyUsage "
                          "keyCertSign+cRLSign (critical); SKI; AKI",
            "end_entity_profile": "BasicConstraints CA=false (critical); KeyUsage "
                                  "digitalSignature (critical); ExtendedKeyUsage "
                                  "emailProtection; SKI; AKI",
            "tsa": None,
            "files": {n: hashlib.sha256(d).hexdigest() for n, d in pki.items()},
        },
        "trap": {"host": TRAP_HOST, "port": TRAP_PORT, "remote_url": REMOTE_URL},
        "fixtures": {n: {"sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d),
                         "params": params[n]} for n, d in sorted(fixtures.items())},
    }
    (out / "manifest.json").write_text(json.dumps(record, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
    for n, d in sorted(fixtures.items()):
        print(f"{n}: {hashlib.sha256(d).hexdigest()} ({len(d)} bytes)")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
