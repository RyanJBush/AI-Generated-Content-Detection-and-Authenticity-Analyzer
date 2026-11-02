"""Read all reachable Git objects; report credential patterns without values."""

import argparse
import json
import re
import subprocess
from pathlib import Path

PATTERNS = {
    "provider_token": rb"(?:sk-ant-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}"
    rb"|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16})",
    "private_key": rb"-----BEGIN (?:(?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?"
    rb"PRIVATE KEY|PGP PRIVATE KEY BLOCK)-----",
    "credential_url": rb"https?://[^\s/@:]+:[^\s/@]+@",
}
TEST_KEYS = {
    "418cc07049c69cb581232e91d916077035b51dfb": (
        "tests/fixtures/c2pa/pki/test_signer_key.pem"
    ),
    "047d0584a55b6c8194a8807a0fb32e81b2ea0fa1": (
        "tests/fixtures/c2pa/pki/untrusted_signer_key.pem"
    ),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path,
                        default=Path('eval/results/publication/history_audit.json'))
    args = parser.parse_args()
    patterns = {name: re.compile(pattern) for name, pattern in PATTERNS.items()}
    objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"])
    findings, prohibited_paths, counts = [], [], {}
    total = 0
    with subprocess.Popen(
        ["git", "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ) as process:
        for entry in objects.splitlines():
            oid, _, path = entry.partition(b" ")
            process.stdin.write(oid + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().split()
            kind, size = header[1].decode(), int(header[2])
            data = process.stdout.read(size)
            assert len(data) == size and process.stdout.read(1) == b"\n"
            counts[kind] = counts.get(kind, 0) + 1
            total += size
            name = path.decode("utf-8", "replace")
            if re.search(
                r"(^|/)(\.env(?:\.|$)|models/|data/raid/)"
                r"|\.safetensors$|train\.csv$",
                name,
            ):
                prohibited_paths.append(name)
            for rule, pattern in patterns.items():
                if pattern.search(data):
                    allowed = (
                        rule == "private_key" and TEST_KEYS.get(oid.decode()) == name
                    )
                    findings.append(
                        {
                            "kind": rule,
                            "path": name,
                            "object": oid.decode(),
                            "documented_test_key": allowed,
                        }
                    )
        process.stdin.close()
        assert process.wait() == 0
    result = {
        "scope": "all reachable Git objects, including commit/tag metadata",
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "objects": counts,
        "bytes": total,
        "findings": findings,
        "prohibited_paths": prohibited_paths,
        "limitations": "Pattern/path scan, not proof of absence of unknown secret "
        "formats or raw text concealed under another name. Existing author email "
        "and Windows paths are retained for private publication.",
    }
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result, indent=2))
    if prohibited_paths or any(not item["documented_test_key"] for item in findings):
        raise SystemExit("Unexpected audit finding: inspect before publication")


if __name__ == "__main__":
    main()
