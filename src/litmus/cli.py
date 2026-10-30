import argparse
import json
import os
import sys
from pathlib import Path

from litmus.errors import C2paUnavailable
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
    analyze.add_argument(
        "--text-origin", choices=["placeholder", "binoculars"],
        default="placeholder",
        help="text origin analyzer (binoculars needs models/; uncalibrated in R1-B1)",
    )
    analyze.add_argument("--models-dir", metavar="DIR",
                         help="model directory (default: <repo>/models)")
    analyze.add_argument("--device", choices=["cuda", "cpu"],
                         help="scorer device (default: cuda if available)")
    analyze.add_argument(
        "--c2pa", choices=["off", "on"], default="off",
        help="image provenance only (default: off); remote manifests are not fetched",
    )
    analyze.add_argument(
        "--quality", choices=["off", "on"], default="off",
        help="text quality observers (default: off); quality observations do "
             "not establish AI origin and never affect origin results",
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

    text_origin = None
    if args.text_origin == "binoculars":
        from litmus.scorer.analyzer import BinocularsAnalyzer
        text_origin = BinocularsAnalyzer(models_dir=args.models_dir,
                                         device=args.device)

    quality_observers = None
    if args.quality == "on":
        # Lexicons load here, before analysis starts
        from litmus.quality.observers import build_observers
        quality_observers = build_observers()

    try:
        report = run_analysis(args.file, text_origin, quality_observers,
                              c2pa_enabled=args.c2pa == "on")
    except C2paUnavailable as exc:
        print(f"litmus: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, indent=2) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
