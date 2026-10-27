import argparse
import json
import os
import sys

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


def main(argv=None) -> int:
    args = _parser().parse_args(argv)

    if not os.path.isfile(args.file):
        print(f"litmus: not a file: {args.file}", file=sys.stderr)
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
