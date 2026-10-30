"""R1-B2 synthetic benchmark inputs -> eval/inputs/r1b2/ (+ manifest.json).

Seeded word salad from a fixed built-in word list (no dataset text). Each text
tokenizes, under the production preprocessing (litmus.scorer.tokenize, observer
tokenizer, add_special_tokens=False, split_special_tokens=True), to EXACTLY its
target length. Every file is re-tokenized after writing to confirm the count.

    .venv\\Scripts\\python.exe scripts\\r1b2_inputs.py [--out DIR]
"""
import argparse
import hashlib
import json
import os
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "eval" / "inputs" / "r1b2"
LENGTHS = (64, 128, 256, 512)
TEXTS_PER_LENGTH = 10
BASE_SEED = 20261030

WORDS = """
time year people way day man thing woman life child world school state family
student group country problem hand part place case week company system program
question work government number night point home water room mother area money
story fact month lot right study book eye job word business issue side kind
head house service friend father power hour game line end member law car city
community name president team minute idea kid body information back parent face
others level office door health person art war history party result change
morning reason research girl guy moment air teacher force education foot boy
age policy music market sense nation plan college interest death experience
effect use class control care field development role effort rate heart drug
show leader light voice wife police mind price report decision son view
relationship town road arm difference value building action model season
society tax director position player record paper space ground form event
official matter center couple site project activity star table need court
oil situation cost industry figure street image phone data picture practice
piece land product doctor wall patient worker news test movie north love
support technology step baby computer type attention film tree source organization
hair window evidence population site board river garden bridge station
make go see know take come think look want give find tell ask seem feel try
leave call keep put mean become begin help talk turn start show hear play run
move like live believe hold bring happen write provide sit stand lose pay meet
include continue set learn change lead understand watch follow stop create
speak read allow add spend grow open walk win offer remember consider appear
buy wait serve die send expect build stay fall cut reach kill remain suggest
raise pass sell require report decide pull
good new first last long great little own other old right big high different
small large next early young important few public bad same able late hard
major better economic strong possible whole free military true federal
political special clear recent certain personal open red difficult available
likely short single medical current wrong private past foreign fine common poor
natural significant similar hot dead central happy serious ready simple left
physical general environmental financial blue democratic dark various entire
close legal religious cold final main green nice huge popular traditional
quietly often never always again still also very really almost already
perhaps together later soon usually slowly quickly simply nearly rather
""".split()
# Single-token connectives used to land exactly on the target length
FILLERS = (" the", " a", " and", " of", " to", " in", " it", " is")


def _count(tokenizer, text):
    from litmus.scorer.tokenize import tokenize_window

    return tokenize_window(tokenizer, text).tokens_total


def _pieces(rng):
    """Endless stream of text pieces forming sentences of 6-14 words."""
    first = True
    while True:
        n = rng.randint(6, 14)
        for i in range(n):
            word = rng.choice(WORDS)
            if i == 0:
                word = word.capitalize()
            yield (word if first else " " + word) + ("." if i == n - 1 else "")
            first = False


def generate(tokenizer, n_tokens, seed, count=_count):
    """Deterministic text with exactly n_tokens tokens under ``count``."""
    rng = random.Random(seed)
    text = ""
    for piece in _pieces(rng):
        c = count(tokenizer, text + piece)
        if c <= n_tokens:
            text += piece
            if c == n_tokens:
                return text
            continue
        # The piece overshoots: close the gap with single-token fillers
        for _ in range(n_tokens):
            have = count(tokenizer, text)
            if have == n_tokens:
                return text
            for filler in FILLERS:
                if count(tokenizer, text + filler) == have + 1:
                    text += filler
                    break
            else:
                raise RuntimeError(f"no filler advances by one token at {have}")
        raise RuntimeError("filler loop did not converge")


def seed_for(n_tokens, index):
    return BASE_SEED + 1000 * n_tokens + index


def file_name(n_tokens, index):
    return f"len{n_tokens:03d}_{index:02d}.txt"


def load_tokenizer(models_dir=None):
    """The production observer tokenizer, loaded offline from models/."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from transformers import AutoTokenizer

    from litmus import config
    from litmus.scorer.loader import default_models_dir

    models_dir = pathlib.Path(models_dir or default_models_dir())
    observer_dir = models_dir / config.OBSERVER_DIR
    sha = hashlib.sha256((observer_dir / "tokenizer.json").read_bytes()).hexdigest()
    if sha != config.TOKENIZER_JSON_SHA256:
        raise RuntimeError(f"tokenizer.json SHA-256 {sha} is not the pinned value")
    return AutoTokenizer.from_pretrained(observer_dir, local_files_only=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    tokenizer = load_tokenizer()
    args.out.mkdir(parents=True, exist_ok=True)
    entries = []
    for n in LENGTHS:
        for i in range(TEXTS_PER_LENGTH):
            text = generate(tokenizer, n, seed_for(n, i))
            path = args.out / file_name(n, i)
            data = text.encode("ascii")
            path.write_bytes(data)
            # Re-tokenize what was written, decoded the way ingestion decodes
            recount = _count(tokenizer, path.read_bytes().decode("utf-8"))
            if recount != n:
                raise SystemExit(f"{path.name}: {recount} tokens, expected {n}")
            entries.append({"file": path.name, "target_tokens": n,
                            "tokens_verified": recount, "seed": seed_for(n, i),
                            "chars": len(text),
                            "sha256": hashlib.sha256(data).hexdigest()})
            print(f"{path.name}: tokens={recount} chars={len(text)}")
    texts = [e["sha256"] for e in entries]
    if len(set(texts)) != len(texts):
        raise SystemExit("duplicate texts generated")
    manifest = {
        "generator": "scripts/r1b2_inputs.py", "base_seed": BASE_SEED,
        "preprocessing": "litmus.scorer.tokenize.tokenize_window (tokens_total)",
        "tokenizer_json_sha256": _pinned_tokenizer_sha(), "files": entries,
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} texts and manifest.json to {args.out}")
    return 0


def _pinned_tokenizer_sha():
    from litmus import config

    return config.TOKENIZER_JSON_SHA256


if __name__ == "__main__":
    sys.exit(main())
