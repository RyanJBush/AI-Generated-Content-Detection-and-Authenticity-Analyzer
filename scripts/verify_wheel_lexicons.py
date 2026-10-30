"""R1-C1/R1-C2 installed-wheel check (plan §d, §j). Run with the TEMPORARY venv's
interpreter in isolated mode, from a directory outside the repository:

    <tmp>\\venv\\Scripts\\python.exe -I scripts\\verify_wheel_lexicons.py \\
        --venv <tmp>\\venv --expect NAME=SHA256 [--expect NAME=SHA256 ...]

Asserts: (a) litmus is imported from inside --venv, not the repository;
(b) the packaged lexicon resources are exactly the expected names;
(c) each resource's SHA-256 equals the expected (source-file) value;
(d) the loader/validator accepts every lexicon; (e) torch and transformers are
not importable here, yet the C1 modules import and work, and neither they nor
the scorer stack end up in sys.modules; (f) (R1-C2) the four observers are
constructed and run, with the expected counts on a fixed sample. Exits 1 on
any failure.
"""
import argparse
import hashlib
import importlib.resources
import importlib.util
import os
import pathlib
import sys

failures = []

OBSERVER_SAMPLE = ("It is important to note that studies show a clear trend. "
                   "Perhaps the data shows more. The cat sat on the mat. "
                   "The cat sat on the mat. In conclusion, it seems likely.")
OBSERVER_EXPECTED = {"stock_phrases": 2, "hedges": 3, "repeated_word_3grams": 8,
                     "claim_phrases_to_inspect": 2}


def check(ok, message):
    print(("PASS " if ok else "FAIL ") + message)
    if not ok:
        failures.append(message)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--venv", required=True, type=pathlib.Path)
    ap.add_argument("--expect", action="append", default=[], metavar="NAME=SHA256")
    args = ap.parse_args(argv)
    expected = dict(e.split("=", 1) for e in args.expect)
    venv = args.venv.resolve()
    print(f"python: {sys.executable}")
    print(f"cwd: {os.getcwd()}")
    print(f"isolated flag (-I): {bool(sys.flags.isolated)}")
    check(bool(sys.flags.isolated), "interpreter runs in isolated mode (-I)")

    # (e, first half) the model stack is absent from this environment
    for mod in ("torch", "transformers"):
        check(importlib.util.find_spec(mod) is None, f"{mod} is not importable")

    import litmus
    import litmus.quality
    from litmus.quality import lexicon, matcher, observers, words

    location = pathlib.Path(litmus.__file__).resolve()
    print(f"litmus.__file__: {location}")
    # (a)
    check(location.is_relative_to(venv), "litmus is imported from inside --venv")

    # (b)
    found = sorted(p.name for p in importlib.resources.files("litmus.quality")
                   .joinpath("lexicons").iterdir() if p.name.endswith(".txt"))
    want = sorted(f"{n}.txt" for n in expected)
    print(f"lexicon resources: {found}")
    check(found == want, f"lexicon resources are exactly {want}")
    check(sorted(lexicon.LEXICON_NAMES) == sorted(expected),
          "LEXICON_NAMES matches the expected names")

    for name, sha in sorted(expected.items()):
        data = lexicon.resource_bytes(name)
        got = hashlib.sha256(data).hexdigest()
        print(f"{name}.txt sha256={got}")
        # (c)
        check(got == sha, f"{name}: resource SHA-256 equals the source file's")
        # (d)
        try:
            lx = lexicon.load_lexicon(name)
        except lexicon.LexiconError as e:
            check(False, f"{name}: loader/validator accepts it ({e})")
            continue
        check(lx.sha256 == sha and len(lx.entries) > 0,
              f"{name}: loader/validator accepts it (v{lx.version}, "
              f"{len(lx.entries)} entries)")
        spans = matcher.find_spans(matcher.compile_entries(lx.entries),
                                   f"x {lx.entries[0]} y")
        check(len(spans) == 1, f"{name}: compiled entries match a listed entry")
    check(words.word_index("C1 modules import anyway").count == 4,
          "word index works")

    # (f) all four observers, constructed and run from the installed package
    records = observers.observe_all(OBSERVER_SAMPLE, observers.build_observers())
    got = {r.observer_id: r.count for r in records}
    print(f"observer counts: {got}")
    check(got == OBSERVER_EXPECTED, f"observer counts equal {OBSERVER_EXPECTED}")

    # (e, second half)
    loaded = sorted(m for m in sys.modules
                    if m.split(".")[0] in ("torch", "transformers")
                    or m == "litmus.scorer" or m.startswith("litmus.scorer."))
    check(not loaded, f"no torch/transformers/scorer modules loaded ({loaded})")

    print(f"RESULT: {'FAIL' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
