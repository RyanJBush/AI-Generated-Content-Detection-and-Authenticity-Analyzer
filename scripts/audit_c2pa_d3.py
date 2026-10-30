"""Audit changed/new Python files for literal non-ASCII outside comments/docs."""
import argparse
import ast
import io
import json
import pathlib
import subprocess
import tokenize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="0c6fa08")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]

    def git(*parts):
        output = subprocess.check_output(["git", *parts], cwd=root, text=True)
        return output.splitlines()

    files = sorted({p for p in git("diff", args.base, "--name-only") +
                    git("ls-files", "--others", "--exclude-standard")
                    if p.endswith(".py")})
    findings = []
    for name in files:
        source = (root / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        doc_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)) and node.body:
                first = node.body[0]
                if (isinstance(first, ast.Expr) and
                        isinstance(first.value, ast.Constant)):
                    if isinstance(first.value.value, str):
                        doc_lines.update(range(first.lineno, first.end_lineno + 1))
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            non_ascii = sorted({f"U+{ord(c):04X}" for c in token.string
                                if ord(c) > 127})
            if non_ascii:
                kind = ("comment" if token.type == tokenize.COMMENT else
                        "docstring" if token.type == tokenize.STRING and
                        token.start[0] in doc_lines else "code_or_runtime_literal")
                findings.append({"file": name, "line": token.start[0],
                                 "kind": kind, "codepoints": non_ascii})
    violations = [f for f in findings if f["kind"] == "code_or_runtime_literal"]
    result = {"status": "FAIL" if violations else "PASS", "base": args.base,
              "scope": "changed and new Python files; comments/docstrings inventoried",
              "files": files, "findings": findings, "violations": violations}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8",
                           newline="\n")
    print(f"{result['status']}: {len(files)} Python files, "
          f"{len(findings)} comment/docstring findings, {len(violations)} violations")
    if violations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
