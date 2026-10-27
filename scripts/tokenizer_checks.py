"""R1-A tokenizer checks -> eval/results/r1a_tokenizer_checks.json.

Offline: tokenizers load from models/ with local_files_only=True and
HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE set. Run from the repository root:
    .venv\\Scripts\\python.exe scripts\\tokenizer_checks.py

Every probe uses a freshly loaded tokenizer with split_special_tokens set at
load time, and passes add_special_tokens explicitly (or omits it, recorded as
"omitted"). Each probe is also repeated with both settings passed explicitly
at call time on the same fresh tokenizer, and the two ID lists are compared.
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import tokenizers  # noqa: E402  (offline env must be set before import)
import transformers  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
OUT = ROOT / "eval" / "results" / "r1a_tokenizer_checks.json"
MODELS = ["Qwen2.5-0.5B", "Qwen2.5-0.5B-Instruct"]

FIXTURES = {
    "english": "The quick brown fox jumps over the lazy dog. "
               "It was a bright cold day in April, and the clocks were striking.",
    "unicode": "Café naïve — emoji \U0001F600\U0001F44D\U0001F3FD "
               "and CJK 漢字かなカナ 한국어.",
    "zero_width_space": "zero​width​space inside​words",
    # Cyrillic Т (U+0422), е (U+0435), о (U+043E), а (U+0430) in Latin-looking words
    "cyrillic_homoglyphs": "Тhе Cyrillic lооks Lаtin",
    "literal_special_tokens": "Before <|endoftext|> middle <|im_end|> after "
                              "<|im_start|>user",
}
ADD_SPECIAL = {"omitted": None, "true": True, "false": False}
SPLIT_SPECIAL = {"false": False, "true": True}


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str, split_special_tokens: bool):
    return AutoTokenizer.from_pretrained(
        MODELS_DIR / name, local_files_only=True,
        split_special_tokens=split_special_tokens,
    )


def encode(tok, text, add_special, split_at_call=None):
    kwargs = {}
    if add_special is not None:
        kwargs["add_special_tokens"] = add_special
    if split_at_call is not None:
        kwargs["split_special_tokens"] = split_at_call
    return tok(text, **kwargs)["input_ids"]


def probe_key(fname, split_key, add_key):
    return (f"{fname}|split_special_tokens={split_key}"
            f"|add_special_tokens={add_key}")


def added_tokens(tok):
    return {str(i): {"content": t.content, "special": t.special}
            for i, t in sorted(tok.added_tokens_decoder.items())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT))
    out_path = pathlib.Path(parser.parse_args().out)

    tok_json = {n: sha256_file(MODELS_DIR / n / "tokenizer.json") for n in MODELS}
    base = {n: load(n, False) for n in MODELS}
    a, b = (base[n] for n in MODELS)

    vocab_equal = a.get_vocab() == b.get_vocab()
    added_a, added_b = added_tokens(a), added_tokens(b)

    probes = {}
    for fname, text in FIXTURES.items():
        for split_key, split in SPLIT_SPECIAL.items():
            for add_key, add in ADD_SPECIAL.items():
                key = probe_key(fname, split_key, add_key)
                entry = {}
                for name in MODELS:
                    tok = load(name, split)  # fresh tokenizer per probe
                    assert tok.split_special_tokens is split
                    ids = encode(tok, text, add)
                    ids_call = encode(load(name, split), text, add, split_at_call=split)
                    entry[name] = {
                        "ids": ids,
                        "tokens": tok.convert_ids_to_tokens(ids),
                        "n": len(ids),
                        "call_time_settings_agree": ids == ids_call,
                    }
                entry["models_agree"] = (entry[MODELS[0]]["ids"]
                                         == entry[MODELS[1]]["ids"])
                probes[key] = entry

    def ids_of(fname, split_key, add_key, name=MODELS[0]):
        return probes[probe_key(fname, split_key, add_key)][name]["ids"]

    summary = {
        "tokenizer_json_identical": len(set(tok_json.values())) == 1,
        "vocab_equal": vocab_equal,
        "vocab_size": len(a.get_vocab()),
        "added_tokens_equal": added_a == added_b,
        "special_tokens_map_equal": a.special_tokens_map == b.special_tokens_map,
        "all_probes_models_agree": all(p["models_agree"] for p in probes.values()),
        "all_probes_call_time_settings_agree": all(
            p[n]["call_time_settings_agree"] for p in probes.values() for n in MODELS),
        "add_special_tokens_changes_ids": any(
            ids_of(f, s, "true") != ids_of(f, s, "false")
            or ids_of(f, s, "omitted") != ids_of(f, s, "false")
            for f in FIXTURES for s in SPLIT_SPECIAL),
        "split_special_tokens_changes_ids_for": sorted(
            f for f in FIXTURES
            if ids_of(f, "false", "false") != ids_of(f, "true", "false")),
    }

    result = {
        "check": "r1a_tokenizer_checks",
        "versions": {"transformers": transformers.__version__,
                     "tokenizers": tokenizers.__version__,
                     "python": sys.version.split()[0]},
        "tokenizer_class": {n: type(base[n]).__name__ for n in MODELS},
        "tokenizer_json_sha256": tok_json,
        "added_tokens": {MODELS[0]: added_a,
                         MODELS[1]: added_b if added_b != added_a else "same as above"},
        "special_tokens_map": {n: base[n].special_tokens_map for n in MODELS},
        "fixtures": FIXTURES,
        "summary": summary,
        "proposal": {
            "status": "PROPOSED for review; not final",
            "split_special_tokens": True,
            "add_special_tokens": False,
            "rationale": (
                "With split_special_tokens=False, literal control strings in "
                "analyzed text (e.g. '<|endoftext|>', '<|im_end|>') become the "
                "models' control-token IDs, so untrusted input could inject "
                "end-of-text or chat-turn tokens into the scored sequence. With "
                "True they are tokenized as ordinary text. add_special_tokens has "
                "no observed effect on these fixtures (no BOS/EOS is added); "
                "False is proposed to match Addendum A4 explicitly."
            ),
        },
        "probes": probes,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
