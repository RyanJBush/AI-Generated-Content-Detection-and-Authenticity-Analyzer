"""Build/install Litmus offline; verify the wheel using existing venv runtimes.

Run with the repository's existing .venv interpreter. No dependency installs,
downloads or environment replacements. The child runs -I outside the repo,
prepends the new --target installation, and checks every loaded Litmus module's
file location so the editable install cannot mask a missing wheel module.
"""
import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import zipfile


def verify(args):
    target, repo = args.target.resolve(), args.repo.resolve()
    assert pathlib.Path.cwd().resolve() != repo
    assert sys.flags.isolated
    sys.path.insert(0, str(target))
    import litmus
    from litmus.c2pa.trust_list import load_production_trust_list, resource_bytes
    from litmus.cli import main

    assert pathlib.Path(litmus.__file__).resolve().is_relative_to(target)
    with zipfile.ZipFile(args.wheel) as wheel:
        names = wheel.namelist()
    assert not any("tests/" in n or "/pki/" in n or n.endswith(".key")
                   or "test_root" in n for n in names)
    assert "litmus/c2pa/trust/production_trust_anchors.pem" in names
    assert [n for n in names if n.endswith(".pem")] == [
        "litmus/c2pa/trust/production_trust_anchors.pem"]
    data = resource_bytes("production_trust_anchors")
    assert hashlib.sha256(data).hexdigest() == args.expect_sha
    trust = load_production_trust_list()
    assert trust.anchors == ()

    # Existing .venv site-packages remains available under -I. Only Litmus is
    # installed into target. No sys.path entry to the repository is added.
    import c2pa
    import PIL
    runtime_root = pathlib.Path(sys.prefix).resolve()
    assert pathlib.Path(c2pa.__file__).resolve().is_relative_to(runtime_root)
    assert pathlib.Path(PIL.__file__).resolve().is_relative_to(runtime_root)
    assert importlib.metadata.version("c2pa-python") == "0.38.0"
    assert PIL.__version__ == "13.0.0"
    assert c2pa.sdk_version() == "0.91.0"
    fixtures = repo / "tests/fixtures/c2pa"
    for ext in ("jpg", "png", "webp"):
        out = pathlib.Path.cwd() / f"installed_{ext}.json"
        assert main(["analyze", str(fixtures / f"trusted_signer.{ext}"),
                     "--c2pa", "on", "-o", str(out)]) == 0
        record = json.loads(out.read_text(encoding="utf-8"))
        origin = record["segments"][0]["origin"][0]
        assert origin["method_id"] == "c2pa_provenance"
        assert origin["provenance"]["active"]["signer_trust"] == "unknown"
        assert origin["provenance"]["trust_list"]["sha256"] == args.expect_sha
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        assert main(["analyze", str(repo / "tests/fixtures/inputs/image.jpg")]) == 0
    assert stream.getvalue() == (repo / "tests/golden/image_jpg.json").read_text(
        encoding="utf-8")
    locations = {}
    for name, module in sys.modules.copy().items():
        if name == "litmus" or name.startswith("litmus."):
            location = pathlib.Path(module.__file__).resolve()
            assert location.is_relative_to(target), (name, str(location))
            locations[name] = str(location)
    assert not any(m == "torch" or m.startswith("torch.") or
                   m == "transformers" or m.startswith("transformers.") or
                   m.startswith("litmus.scorer") for m in sys.modules)
    result = {
        "status": "PASS", "isolated": True, "cwd": str(pathlib.Path.cwd()),
        "installed_target": str(target), "wheel": str(args.wheel),
        "runtime_dependency_source": str(runtime_root),
        "runtime_versions": {"pillow": PIL.__version__, "c2pa_python": "0.38.0",
                             "sdk": c2pa.sdk_version()},
        "trust_sha256": args.expect_sha, "trust_anchor_count": 0,
        "all_loaded_litmus_modules_from_wheel": locations,
        "enabled_formats_passed": ["jpeg", "png", "webp"],
        "default_image_golden": "PASS", "test_keys_and_anchors_packaged": False,
    }
    print(json.dumps(result))


def run(command, cwd):
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(f"{command!r}\n{completed.stdout}\n{completed.stderr}")
    return completed.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--target", type=pathlib.Path)
    parser.add_argument("--repo", type=pathlib.Path)
    parser.add_argument("--wheel", type=pathlib.Path)
    parser.add_argument("--expect-sha")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    if args.verify:
        verify(args)
        return
    repo = pathlib.Path(__file__).resolve().parents[1]
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="litmus-d3-wheel-"))
    before = run([sys.executable, "-m", "pip", "freeze", "--all"], scratch)
    commands = []
    command = [sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps",
               "--no-build-isolation", "--no-cache-dir", "--wheel-dir",
               str(scratch / "wheels"), str(repo)]
    commands.append(command)
    run(command, scratch)
    wheel, = (scratch / "wheels").glob("*.whl")
    command = [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
               "--no-compile", "--target", str(scratch / "installed"), str(wheel)]
    commands.append(command)
    run(command, scratch)
    sha = hashlib.sha256((repo / "src/litmus/c2pa/trust/"
                         "production_trust_anchors.pem").read_bytes()).hexdigest()
    command = [sys.executable, "-I", str(pathlib.Path(__file__).resolve()),
               "--verify", "--target", str(scratch / "installed"), "--repo",
               str(repo), "--wheel", str(wheel), "--expect-sha", sha]
    commands.append(command)
    result = json.loads(run(command, scratch))
    after = run([sys.executable, "-m", "pip", "freeze", "--all"], scratch)
    assert before == after, "existing venv distribution list changed"
    result["existing_venv_distributions_unchanged"] = True
    result["commands"] = commands
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
