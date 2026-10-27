import argparse
import json
import os
import sys
from pathlib import Path

from litmus.report import run_analysis


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="litmus")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="analyze FILE and write a report JSON")
    analyze.add_argument("file", metavar="FILE")
    analyze.add_argument(
        "-o", "--output", metavar="PATH",
        help="write the report to PATH instead of standard output",
    )
    return parser


def _is_same_file(input_path: str, output_path: str) -> bool:
    """True if writing output_path would overwrite input_path."""
    if os.path.exists(output_path):
        # Catches hard links and any other alias of the same file
        return os.path.samefile(input_path, output_path)
    resolved_in = os.path.normcase(str(Path(input_path).resolve()))
    resolved_out = os.path.normcase(str(Path(output_path).resolve()))
    return resolved_in == resolved_out


def main(argv=None) -> int:
    args = _parser().parse_args(argv)

    if not os.path.isfile(args.file):
        print(f"litmus: not a file: {args.file}", file=sys.stderr)
        return 1

    # Checked before analysis so nothing is written or modified on rejection
    if args.output and _is_same_file(args.file, args.output):
        print(
            f"litmus: refusing to overwrite the input file: {args.output} "
            f"is the same file as {args.file}",
            file=sys.stderr,
        )
        return 1

    report = run_analysis(args.file)
    text = json.dumps(report, indent=2) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
