"""Setup command: download the pinned R1 text model pair into models/ (R1-A).

This is the ONLY network-enabled entry point (SPEC §7 "Setup commands").
Usage (from the repository root):
    .venv\\Scripts\\python.exe scripts\\download_models.py [--only NAME] [--verify-only]

Each repository is fetched at an exact commit SHA. After download, every file's
SHA-256 is computed; model.safetensors must match the published value or the
script exits non-zero without updating the manifest. The manifest of file
hashes (not the weights) is written to models.manifest.json for commit.
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
MANIFEST = ROOT / "models.manifest.json"

# Pinned in R1-PLAN.md §1.1; safetensors SHA-256 published by the HF API
MODELS = {
    "Qwen2.5-0.5B": {
        "repo_id": "Qwen/Qwen2.5-0.5B",
        "revision": "060db6499f32faf8b98477b0a26969ef7d8b9987",
        "model_safetensors_sha256":
            "88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342",
    },
    "Qwen2.5-0.5B-Instruct": {
        "repo_id": "Qwen/Qwen2.5-0.5B-Instruct",
        "revision": "7ae557604adf67be50417f59c2c2f167def9a775",
        "model_safetensors_sha256":
            "fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe",
    },
}


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_files(local_dir: pathlib.Path):
    """All downloaded files, excluding huggingface_hub's local .cache metadata."""
    for path in sorted(local_dir.rglob("*")):
        rel = path.relative_to(local_dir)
        if path.is_file() and rel.parts[0] != ".cache":
            yield rel.as_posix(), path


def download(name: str, spec: dict) -> None:
    # Network is permitted only here, so lift any offline flags for this call
    for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        os.environ.pop(var, None)
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=spec["repo_id"],
        revision=spec["revision"],
        local_dir=MODELS_DIR / name,
    )


def verify(name: str, spec: dict) -> dict:
    local_dir = MODELS_DIR / name
    files = {rel: {"sha256": sha256_file(p), "size": p.stat().st_size}
             for rel, p in model_files(local_dir)}
    if "model.safetensors" not in files:
        raise SystemExit(f"{name}: model.safetensors missing in {local_dir}")
    got = files["model.safetensors"]["sha256"]
    want = spec["model_safetensors_sha256"]
    print(f"{name}: model.safetensors sha256 {got}")
    print(f"{name}: expected              {want}")
    if got != want:
        raise SystemExit(f"{name}: SHA-256 MISMATCH for model.safetensors; STOP")
    print(f"{name}: model.safetensors SHA-256 matches")
    return {"repo_id": spec["repo_id"], "revision": spec["revision"],
            "files": files}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=sorted(MODELS))
    parser.add_argument("--verify-only", action="store_true",
                        help="hash local files; no network")
    args = parser.parse_args()

    names = [args.only] if args.only else list(MODELS)
    manifest = {}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    for name in names:
        if not args.verify_only:
            download(name, MODELS[name])
        manifest[name] = verify(name, MODELS[name])

    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(f"wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
