"""`litmus score FILE`: print a report JSON (SPEC §3.3) for one UTF-8 text file."""
import argparse
import sys

from litmus import config
from litmus.calibration import CALIBRATION_DIR, load_calibration
from litmus.identity import compute_identity
from litmus.report import build_report, report_to_json
from litmus.scoring import DTYPES, load_pair, score_text
from litmus.slop import analyze


class Analyzer:
    """Loaded pair + identity + calibration lookup, shared by the CLI and the app."""

    def __init__(self, pair, calibration_dir=CALIBRATION_DIR):
        self.pair = pair
        self.identity = compute_identity(pair)
        self.calibration = load_calibration(self.identity, calibration_dir)

    def report(self, text):
        return build_report(text, score_text(text, self.pair), analyze(text), self.identity, self.calibration)


def read_text(path):
    # newline="" keeps \r\n and \r as written, so report offsets index the file's original characters.
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def main(argv=None, load=load_pair):
    parser = argparse.ArgumentParser(prog="litmus")
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("score", help="score one UTF-8 text file and print a report JSON")
    score.add_argument("file")
    score.add_argument("--pair", choices=sorted(config.PAIRS), default=config.DEFAULT_PAIR)
    score.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    score.add_argument("--dtype", choices=sorted(DTYPES), default="float32")
    score.add_argument("--calibration-dir", default=str(CALIBRATION_DIR))
    score.add_argument("--output", help="also write the report JSON to this path")
    args = parser.parse_args(argv)

    try:
        text = read_text(args.file)
    except (OSError, UnicodeDecodeError) as e:
        print(f"litmus: cannot read {args.file}: {e}", file=sys.stderr)
        return 2

    analyzer = Analyzer(load(args.pair, device=args.device, dtype=args.dtype), args.calibration_dir)
    output = report_to_json(analyzer.report(text))
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(output + "\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
