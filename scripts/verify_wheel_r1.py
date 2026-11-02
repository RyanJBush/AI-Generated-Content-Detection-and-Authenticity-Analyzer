"""Build/install only Litmus with no downloads; smoke UI/CLI outside the checkout.

The existing venv supplies pinned runtime dependencies. Child -I explicitly
prepends the new target and asserts every loaded Litmus module comes from it.
No model weights, dataset blobs, real scoring or native C2PA analysis are used.
"""

import argparse
import contextlib
import http.client
import importlib.metadata
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path


def run(command, cwd):
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def child(args):
    assert sys.flags.isolated
    assert Path.cwd().resolve() != args.repo.resolve()
    sys.path.insert(0, str(args.target.resolve()))
    import litmus
    from litmus.cli import main
    from litmus.local_ui.server import make_server

    assert Path(litmus.__file__).resolve().is_relative_to(args.target.resolve())
    with zipfile.ZipFile(args.wheel) as archive:
        names = archive.namelist()
        assert all(
            "litmus/local_ui/static/" + p in names
            for p in ("index.html", "app.js", "style.css")
        )
        assert not any(
            n.startswith(("data/", "models/", "tests/", "eval/")) or n.endswith(".key")
            for n in names
        )
    fixture = args.repo / "tests/fixtures/inputs/image.jpg"
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        assert main(["analyze", str(fixture)]) == 0
    assert stdout.getvalue() == (args.repo / "tests/golden/image_jpg.json").read_text(
        encoding="utf-8"
    )
    server = make_server(0)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()

    def request(method, path, data=None):
        c = http.client.HTTPConnection(*server.server_address, timeout=5)
        h = {"X-Litmus-Token": server.token}
        if data is not None:
            h.update(
                {
                    "Content-Type": "application/octet-stream",
                    "X-Litmus-Filename": "wheel.txt",
                }
            )
        c.request(method, path, data, h)
        response = c.getresponse()
        result = response.status, response.read()
        c.close()
        return result

    try:
        assert server.server_address[0] == "127.0.0.1"
        assert b"Evidence, not a verdict" in request("GET", "/")[1]
        assert b"not a probability" in request("GET", "/app.js")[1]
        assert request("GET", "/style.css")[0] == 200
        status, body = request(
            "POST",
            "/api/v1/jobs?quality=on",
            b"In conclusion, this is a constructed wheel smoke fixture.",
        )
        assert status == 202
        rid = json.loads(body)["id"]
        for _ in range(200):
            status, body = request("GET", "/api/v1/jobs/" + rid)
            assert status == 200
            job = json.loads(body)
            if job["status"] != "running":
                break
            time.sleep(0.01)
        assert job["status"] == "completed", job
        report = job["report"]
        assert report["input"]["file_name"] == "wheel.txt"
        assert (
            report["segments"][0]["origin"][0]["method_id"] == "text_origin_placeholder"
        )
        assert report["segments"][0]["quality"]
        assert json.loads(json.dumps(report)) == report
    finally:
        server.shutdown()
        server.server_close()
        server.service.close()
        thread.join(3)
    assert not any(
        n.startswith(("torch", "transformers", "litmus.evaluation", "litmus.data_prep"))
        for n in sys.modules
    )
    locations = {}
    for name, module in sys.modules.copy().items():
        if name == "litmus" or name.startswith("litmus."):
            path = Path(module.__file__).resolve()
            assert path.is_relative_to(args.target.resolve()), (name, str(path))
            locations[name] = str(path)
    import PIL

    assert Path(PIL.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    result = {
        "status": "PASS",
        "isolated": True,
        "cwd": str(Path.cwd()),
        "target": str(args.target),
        "wheel": str(args.wheel),
        "runtime_source": str(Path(sys.prefix)),
        "runtime_versions": {
            n: importlib.metadata.version(n)
            for n in ("pillow", "c2pa-python", "torch", "transformers")
        },
        "loaded_litmus_modules_from_fresh_wheel": locations,
        "ui_assets": "PASS",
        "loopback_upload_poll_quality_report_roundtrip": "PASS",
        "default_image_golden": "PASS",
        "models_or_evaluation_imported": False,
        "raw_data_or_weights_packaged": False,
    }
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.child:
        child(args)
        return
    repo = Path(__file__).resolve().parents[1]
    scratch = Path(tempfile.mkdtemp(prefix="litmus-r1-wheel-"))
    before = run([sys.executable, "-m", "pip", "freeze", "--all"], scratch)
    commands = [
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--no-cache-dir",
            "--wheel-dir",
            str(scratch / "wheels"),
            str(repo),
        ]
    ]
    run(commands[-1], scratch)
    (wheel,) = (scratch / "wheels").glob("*.whl")
    target = scratch / "installed"
    commands.append(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--target",
            str(target),
            str(wheel),
        ]
    )
    run(commands[-1], scratch)
    commands.append(
        [
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            "--child",
            "--repo",
            str(repo),
            "--target",
            str(target),
            "--wheel",
            str(wheel),
        ]
    )
    result = json.loads(run(commands[-1], scratch))
    assert before == run([sys.executable, "-m", "pip", "freeze", "--all"], scratch)
    result.update(
        existing_venv_distributions_unchanged=True,
        commands=commands,
        limits=("Model-free wheel packaging only; calibrated CUDA use remains "
                "the pinned source-checkout profile."),
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
