"""R1-D1 real library-output capture -> eval/results/r1d1_library_outputs/.

Evidence for D2 only: no mapping, no rule engine. Every fixture in
tests/fixtures/c2pa/manifest.json (images only) is read with the installed
Reader under two configurations from litmus.c2pa.settings:

- production: production_config() (offline settings, empty anchor list)
- test_anchors: test_anchor_config([tests/fixtures/c2pa/pki/test_root_ca.pem])

For each read the raw outputs are saved: the manifest store JSON
(Reader.json), validation_state, validation_results, and a per-manifest
listing that separates the active manifest from ingredient manifests, plus
every status entry with the list it came from (success / informational /
failure), its URL and the manifest it belongs to. A read that raises records
the exception class and message instead. index.json records the command,
the settings dicts, the library versions and the per-read summary.

    .venv\\Scripts\\python.exe scripts\\capture_c2pa_outputs.py [--out DIR]
"""
import argparse
import datetime
import hashlib
import io
import json
import pathlib
import sys

import c2pa

from litmus.c2pa.settings import build_settings, production_config, test_anchor_config

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "c2pa"
DEFAULT_OUT = ROOT / "eval" / "results" / "r1d1_library_outputs"
MIME = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
LISTS = ("success", "informational", "failure")


def status_entries(results, scope):
    """Flatten one validation-results object into tagged entries."""
    out = []
    for lst in LISTS:
        for entry in (results or {}).get(lst, []) or []:
            out.append({"scope": scope, "list": lst, "code": entry.get("code"),
                        "url": entry.get("url"),
                        "explanation": entry.get("explanation")})
    return out


def manifest_listing(store):
    """Active vs ingredient manifests, with ingredient links as reported."""
    active = store.get("active_manifest")
    listing = []
    for label, manifest in (store.get("manifests") or {}).items():
        listing.append({
            "manifest_label": label,
            "is_active": label == active,
            "title": manifest.get("title"),
            "ingredients": [{
                "title": ing.get("title"),
                "relationship": ing.get("relationship"),
                "active_manifest": ing.get("active_manifest"),
                "validation_status_codes": [
                    v.get("code") for v in ing.get("validation_status", []) or []],
                "validation_results": ing.get("validation_results"),
            } for ing in manifest.get("ingredients", []) or []],
            "actions_digital_source_types": [
                act.get("digitalSourceType")
                for a in manifest.get("assertions", []) or []
                if str(a.get("label", "")).startswith("c2pa.actions")
                for act in (a.get("data") or {}).get("actions", []) or []],
        })
    return listing


def read(name, config):
    data = (FIXTURES / name).read_bytes()
    settings = build_settings(config)
    context = c2pa.Context(settings=settings)
    try:
        reader = c2pa.Reader(MIME[pathlib.Path(name).suffix], io.BytesIO(data),
                             context=context)
        with reader:
            store = json.loads(reader.json())
        results = store.get("validation_results") or {}
        entries = status_entries(results.get("activeManifest"), "activeManifest")
        for i, delta in enumerate(results.get("ingredientDeltas", []) or []):
            entries += status_entries(
                delta.get("validationDeltas"),
                f"ingredientDeltas[{i}] {delta.get('ingredientAssertionURI')}")
        return {"outcome": "read",
                "validation_state": store.get("validation_state"),
                "manifests": manifest_listing(store),
                "status_entries": entries,
                "validation_results": results,
                "manifest_store": store}
    except c2pa.C2paError as e:
        return {"outcome": "exception", "exception_class": type(e).__name__,
                "exception_bases": [b.__name__ for b in type(e).__mro__[1:3]],
                "message": str(e)}
    finally:
        context.close()
        settings.close()


def summary(record):
    if record["outcome"] == "exception":
        return {"outcome": "exception", "exception_class": record["exception_class"],
                "message": record["message"][:300]}
    codes = {}
    for e in record["status_entries"]:
        codes.setdefault(e["scope"], {}).setdefault(e["list"], []).append(e["code"])
    return {"outcome": "read", "validation_state": record["validation_state"],
            "codes": {s: {k: sorted(v) for k, v in lists.items()}
                      for s, lists in codes.items()},
            "manifests": [{"manifest_label": m["manifest_label"],
                           "is_active": m["is_active"],
                           "ingredients": [{"title": i["title"],
                                            "relationship": i["relationship"]}
                                           for i in m["ingredients"]],
                           "digital_source_types": m["actions_digital_source_types"]}
                          for m in record["manifests"]]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    fixture_manifest = json.loads((FIXTURES / "manifest.json").read_text(
        encoding="utf-8"))
    anchor = (FIXTURES / "pki" / "test_root_ca.pem").read_text(encoding="utf-8")
    configs = {"production": production_config(),
               "test_anchors": test_anchor_config([anchor])}
    index = {
        "checkpoint": "R1-D1",
        "captured": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": " ".join([sys.executable] + sys.argv),
        "library": {"c2pa_python": "0.38.0 (dist-info)",
                    "sdk_version": c2pa.sdk_version()},
        "settings_applied_with": "c2pa.Settings.from_dict(config) then "
                                 "c2pa.Context(settings=...); Reader(mime, "
                                 "BytesIO(bytes), context=...)",
        "configs": {k: {kk: (vv if kk != "trust" else {
            "trust_anchors_sha256": hashlib.sha256(
                vv["trust_anchors"].encode()).hexdigest()})
            for kk, vv in v.items()} for k, v in configs.items()},
        "test_anchor": "tests/fixtures/c2pa/pki/test_root_ca.pem",
        "reads": {},
    }
    for name, meta in sorted(fixture_manifest["fixtures"].items()):
        if pathlib.Path(name).suffix not in MIME:
            continue
        for cfg_name, config in configs.items():
            record = read(name, config)
            record = {"fixture": name, "fixture_sha256": meta["sha256"],
                      "config": cfg_name, **record}
            out_name = f"{name.replace('.', '_')}__{cfg_name}.json"
            (args.out / out_name).write_text(json.dumps(record, indent=1) + "\n",
                                             encoding="utf-8", newline="\n")
            index["reads"][f"{name} / {cfg_name}"] = {"file": out_name,
                                                      **summary(record)}
            print(f"{name} / {cfg_name}: {json.dumps(summary(record))}")
    (args.out / "index.json").write_text(json.dumps(index, indent=1) + "\n",
                                         encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
