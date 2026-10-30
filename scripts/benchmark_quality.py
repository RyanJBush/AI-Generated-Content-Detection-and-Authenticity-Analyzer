"""R1-C2 text quality observer benchmark -> eval/results/r1c2_quality_benchmark.json.

Times the four observers (litmus.quality.observers) on synthetic inputs of
10,000 / 50,000 / 200,000 code points, in two kinds:

- typical_prose: a fixed English paragraph with a few lexicon matches,
  repeated and cut to length;
- adversarial_high_match: lexicon phrases back to back, so nearly every word
  is a match and every word 3-gram repeats.

Per input: 1 untimed warmup, then 5 timed runs. Each run times the word index,
each observer's ``observe`` and the total (word index + all four observers,
in the observe_all order), with time.perf_counter(). Observer construction
(lexicon load and compile) is timed once, separately. Inputs are generated
in memory; their SHA-256 values are recorded. The benchmark is not a test.

Suite ``extended`` (R1-C2 corrections) adds 200,000-code-point "a "
repeated, one 200,000-code-point word with no spaces, 200,000 CJK code points
with no spaces, and ordinary prose at 500 / 2,000 / 10,000 code points. Every
input records its generator parameters, exact code-point count and SHA-256.

Any case whose median total exceeds 5 s is flagged "EXCEEDS TARGET -- for
review" (an em dash in the output) with the per-observer breakdown; nothing
here optimizes anything.

Results are never overwritten: if --out exists, the run is appended as a new
timestamped section under "additional_runs"; otherwise the run is written as
the top-level object.

    .venv\\Scripts\\python.exe scripts\\benchmark_quality.py
        [--suite r1c2|extended] [--out PATH]
"""
import argparse
import hashlib
import json
import pathlib
import platform
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from benchmark_r1b2 import cpu_name, now, power_state, ram_bytes, summarize  # noqa: E402

from litmus.offline import offline_guards  # noqa: E402
from litmus.quality.observers import (  # noqa: E402
    OBSERVER_IDS,
    OBSERVER_VERSION,
    build_observers,
    observe_all,
)
from litmus.quality.words import word_index  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "eval" / "results" / "r1c2_quality_benchmark.json"
LENGTHS = (10_000, 50_000, 200_000)
WARMUP_RUNS = 1
TIMED_RUNS = 5
TARGET_SECONDS = 5.0
CJK_BASE = 0x4E00  # CJK Unified Ideographs
CJK_CYCLE = 500

PROSE = (
    "The committee met on Tuesday to review the budget for the coming year. "
    "Most of the discussion concerned the repair schedule for the north bridge, "
    "which has been closed to heavy vehicles since the spring floods. "
    "Engineers presented three options, each with different costs and delays. "
    "It is important to note that the cheapest option would keep one lane "
    "closed until autumn. Some members argued that studies show traffic moves "
    "to the river road when the bridge is closed, and that the local shops "
    "lose trade as a result. Others said the evidence was thin and perhaps "
    "overstated. The chair asked for a written summary of the traffic counts "
    "before the next meeting, and the vote was postponed by two weeks. "
)
ADVERSARIAL = (
    "it is important to note that perhaps studies show it seems likely "
    "in conclusion arguably experts agree delve into "
)


def make_text(unit, length):
    return (unit * (length // len(unit) + 1))[:length]


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repeat(kind, unit_name, unit, n):
    generator = {"method": "repeat unit, cut to n code points",
                 "unit": unit_name, "unit_sha256": _sha(unit), "n": n}
    return kind, generator, make_text(unit, n)


def inputs(suite):
    """(kind, generator parameters, text), deterministic."""
    if suite == "r1c2":
        for kind, unit in (("typical_prose", PROSE),
                           ("adversarial_high_match", ADVERSARIAL)):
            for n in LENGTHS:
                yield _repeat(kind, kind, unit, n)
        return
    yield _repeat("a_space_repeated", "'a '", "a ", 200_000)
    yield ("long_word_no_spaces",
           {"method": "'a' * n", "n": 200_000}, "a" * 200_000)
    yield ("cjk_no_spaces",
           {"method": "chr(base + i % cycle) for i in range(n)",
            "base": f"U+{CJK_BASE:04X}", "cycle": CJK_CYCLE, "n": 200_000},
           "".join(chr(CJK_BASE + i % CJK_CYCLE) for i in range(200_000)))
    for n in (500, 2_000, 10_000):
        yield _repeat("natural_prose", "typical_prose", PROSE, n)


def timed_run(text, observers):
    """One run, timed piecewise; mirrors observe_all (word index built once)."""
    times = {}
    records = []
    start = time.perf_counter()
    words = word_index(text)
    times["word_index"] = time.perf_counter() - start
    for observer in observers:
        t0 = time.perf_counter()
        records.append(observer.observe(text, words))
        times[observer.observer_id] = time.perf_counter() - t0
    times["total"] = time.perf_counter() - start
    return times, records


def measure(kind, generator, text, observers):
    n = len(text)
    expected = observe_all(text, observers)
    with offline_guards():
        for _ in range(WARMUP_RUNS):
            timed_run(text, observers)
        runs = [timed_run(text, observers) for _ in range(TIMED_RUNS)]
    for _, records in runs:
        if records != expected:
            raise SystemExit(f"{kind}/{n}: timed run differs from observe_all")
    keys = ["word_index", *OBSERVER_IDS, "total"]
    summary = {k: summarize([t[k] for t, _ in runs]) for k in keys}
    block = {
        "kind": kind, "generator": generator, "code_points": len(text),
        "sha256_utf8": _sha(text),
        "words": word_index(text).count,
        "counts": {r.observer_id: r.count for r in expected},
        "statuses": {r.observer_id: r.status.value for r in expected},
        "runs_seconds": [t for t, _ in runs],
        "summary_seconds": summary,
        "flag": None,
    }
    if summary["total"]["median"] > TARGET_SECONDS:
        block["flag"] = {
            "status": "EXCEEDS TARGET \u2014 for review",
            "target_seconds": TARGET_SECONDS,
            "median_total_seconds": summary["total"]["median"],
            "median_breakdown_seconds": {k: summary[k]["median"] for k in keys[:-1]},
        }
    return block


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--suite", choices=["r1c2", "extended"], default="r1c2")
    args = ap.parse_args(argv)

    started = now()
    system = {"cpu": cpu_name(), "ram_bytes": ram_bytes(),
              "os": platform.platform(), "python": platform.python_version(),
              "power": power_state()}

    t0 = time.perf_counter()
    observers = build_observers()
    construction = time.perf_counter() - t0
    errors = [r.observer_id for r in observe_all("x", observers)
              if r.status.value == "error"]
    if errors:
        raise SystemExit(f"observer construction failed: {errors}")
    lexicons = {o.observer_id: {"version": o.lexicon.version,
                                "sha256": o.lexicon.sha256}
                for o in observers if getattr(o, "lexicon", None)}

    blocks = []
    for kind, generator, text in inputs(args.suite):
        blocks.append(measure(kind, generator, text, observers))
        s = blocks[-1]["summary_seconds"]
        print(f"[{kind} {len(text)}] words={blocks[-1]['words']} "
              f"counts={blocks[-1]['counts']}", flush=True)
        print("  " + "  ".join(f"{k}: median={v['median']:.4f}s max={v['max']:.4f}s"
                               for k, v in s.items()), flush=True)
        if blocks[-1]["flag"]:
            print(f"  FLAG: {json.dumps(blocks[-1]['flag'])}", flush=True)

    flagged = [f"{b['kind']}/{b['code_points']}" for b in blocks if b["flag"]]
    result = {
        "checkpoint": "R1-C2",
        "suite": args.suite,
        "started": started, "finished": now(),
        "command": " ".join([sys.executable] + sys.argv),
        "definitions": {
            "timer": "time.perf_counter()",
            "p90": "nearest rank: the ceil(0.9*n)-th smallest value",
            "warmup": f"{WARMUP_RUNS} untimed run per input",
            "timed": f"{TIMED_RUNS} runs per input",
            "word_index": "litmus.quality.words.word_index(text), built once per run",
            "per_observer": "observer.observe(text, words) for each observer",
            "total": "word index + the four observe calls, in report order "
                     "(excludes observer construction, decoding and report "
                     "assembly)",
            "construction": "build_observers(): load and compile the three "
                            "lexicons (timed once)",
            "offline": "warmup and timed runs execute under "
                       "litmus.offline.offline_guards()",
            "target": f"median total <= {TARGET_SECONDS} s; every case above it "
                      "is flagged for review, not optimized",
        },
        "system": system,
        "observer_version": OBSERVER_VERSION,
        "lexicons": lexicons,
        "inputs": {"typical_prose_unit_sha256": _sha(PROSE),
                   "adversarial_unit_sha256": _sha(ADVERSARIAL)},
        "construction_seconds": construction,
        "results": blocks,
        "flagged": flagged,
    }
    if args.out.exists():
        # Earlier measurements are kept: append this run as a new section
        data = json.loads(args.out.read_text(encoding="utf-8"))
        data.setdefault("additional_runs", []).append(result)
    else:
        data = result
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"construction: {construction:.4f}s")
    print(f"flagged: {flagged}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
