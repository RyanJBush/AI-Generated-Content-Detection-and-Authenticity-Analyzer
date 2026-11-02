"""Explicit local synthetic CUDA/C2PA check; never reads evaluation text blobs."""

import argparse
import hashlib
import http.client
import json
import threading
import time
from pathlib import Path

from litmus.local_ui.server import make_server


def validate(reports, expected):
    root = Path(__file__).resolve().parents[1]
    freeze = json.loads((root / "eval/freezes/r1f_freeze.json").read_text())["payload"]
    assert len(reports) == 3
    assert reports[0] == reports[1], "Repeated text reports differ"
    for report in reports[:2]:
        assert report["input"]["sha256"] == expected["synthetic_input_sha256"]
        evidence = report["segments"][0]["origin"][0]
        assert evidence["result"] == "no_signal"
        assert evidence["calibration"]["threshold_c"] == freeze["threshold_c"]
        assert (
            evidence["details"]["calibration_artifact_sha256"]
            == freeze["calibration_artifact_sha256"]
        )
        assert evidence["method_id"] == "binoculars"
        assert evidence["raw_score"] == expected["synthetic_result"]["stats"]["score"]
        assert evidence["details"]["scoring_config"] == expected["scoring_config"]
        assert (
            evidence["calibration"]["scoring_config_hash"]
            == expected["scoring_config_hash"]
        )
        assert evidence["reasons"] == ["not_above_calibrated_threshold"]
        assert (
            evidence["details"]["scored_window"]
            == expected["synthetic_result"]["scored_window"]
        )
        for key in ("nll_performer", "xent"):
            assert (
                evidence["details"][key] == expected["synthetic_result"]["stats"][key]
            )
    evidence = reports[2]["segments"][0]["origin"][0]
    fixture = root / "tests/fixtures/c2pa/active_ai_declared.jpg"
    assert (
        reports[2]["input"]["sha256"]
        == hashlib.sha256(fixture.read_bytes()).hexdigest()
    )
    assert evidence["provenance"]["policy"] == "production"
    anchors = root / "src/litmus/c2pa/trust/production_trust_anchors.pem"
    assert (
        evidence["provenance"]["trust_list"]["sha256"]
        == hashlib.sha256(anchors.read_bytes()).hexdigest()
    )
    assert evidence["result"] == "inconclusive"
    assert evidence["reasons"] == ["untrusted_signed_ai_declaration"]
    assert evidence["details"]["settings_applied"] is True
    active = evidence["provenance"]["active"]
    assert active["declared_ai_use"] == "declared"
    assert active["integrity"] == active["signature"] == "valid"
    assert active["signer_trust"] == "unknown"
    assert active["timestamp"] == "absent"
    assert evidence["provenance"]["trust_list"]["anchor_count"] == 0
    assert json.loads(json.dumps(reports)) == reports
    print(
        "PASS: two identical calibrated CUDA reports match frozen synthetic preflight; "
        "constructed C2PA fixture uses production policy; JSON round-trip passes"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-saved", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output or root / "eval/results/publication/ui_engine_reports.json"
    expected = json.loads((root / "eval/results/r1f/preflight_a.json").read_text())
    if args.verify_saved:
        validate(
            json.loads(output.read_text()),
            expected,
        )
        return
    if output.exists():
        raise FileExistsError("Preserving existing reports; choose a new --output path")
    server = make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, data=None, name="synthetic.txt"):
        connection = http.client.HTTPConnection(*server.server_address, timeout=30)
        headers = {"X-Litmus-Token": server.token}
        if data is not None:
            headers.update(
                {"Content-Type": "application/octet-stream", "X-Litmus-Filename": name}
            )
        connection.request(method, path, data, headers)
        response = connection.getresponse()
        status, body = response.status, response.read()
        connection.close()
        return status, json.loads(body)

    def submit(path, options):
        status, job = request(
            "POST", "/api/v1/jobs?" + options, path.read_bytes(), path.name
        )
        assert status == 202, (status, job)
        deadline = time.monotonic() + 300
        while job["status"] == "running":
            assert time.monotonic() < deadline, "Response deadline exceeded"
            time.sleep(0.2)
            status, job = request("GET", "/api/v1/jobs/" + job["id"])
            assert status == 200
        assert job["status"] == "completed", job
        return job["report"]

    reports = []
    try:
        fixture = root / "eval/inputs/r1b2/len512_00.txt"
        assert (
            hashlib.sha256(fixture.read_bytes()).hexdigest()
            == expected["synthetic_input_sha256"]
        )
        for _ in range(2):
            reports.append(submit(fixture, "text_origin=on"))
        reports.append(
            submit(root / "tests/fixtures/c2pa/active_ai_declared.jpg", "c2pa=on")
        )
    finally:
        server.shutdown()
        server.server_close()
        server.service.close()
        thread.join()
    validate(reports, expected)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(reports, indent=2) + "\n")


if __name__ == "__main__":
    main()
