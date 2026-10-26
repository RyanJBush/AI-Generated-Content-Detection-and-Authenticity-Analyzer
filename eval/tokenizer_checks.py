"""Task 1 tokenizer checks (SPEC §3.1 C3/C4) at pinned revisions.

Downloads tokenizer/config files only (no weights). Not a pytest test.
Usage: .venv\\Scripts\\python.exe eval\\tokenizer_checks.py
"""
import hashlib
import itertools
import json
import platform
import sys
from pathlib import Path

import tokenizers
import transformers
from huggingface_hub import hf_hub_download
from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from litmus.config import MODEL_REVISIONS  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent / "results" / "tokenizer_checks.json"

FIXTURES = [
    ("ordinary", "The quick brown fox jumps over the lazy dog."),
    ("unicode", "Café déjà vu — naïve 🌍 résumé"),
    ("zero_width", "A​ B and zero‍width⁠joiners"),
    ("homoglyph", "Tеst wіth Cyrіllіc аnd Grοek"),
    ("literal_endoftext", "Text with <|endoftext|> inside."),
    ("literal_im_end", "Text with <|im_end|> inside."),
    ("literal_im_start", "Text with <|im_start|> inside."),
    ("literal_all", "a <|im_start|>user\nhi<|im_end|> b <|endoftext|> c"),
]

# Encoding modes: name -> kwargs to tokenizer.__call__.
MODES = {
    "add_special_tokens_omitted": {},
    "add_special_tokens_true": {"add_special_tokens": True},
    "add_special_tokens_false": {"add_special_tokens": False},
    "split_special_tokens_false": {"add_special_tokens": False, "split_special_tokens": False},
    "split_special_tokens_true": {"add_special_tokens": False, "split_special_tokens": True},
}


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha256_json(obj):
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def encode(tok, text, kwargs):
    try:
        enc = tok(text, **kwargs)
    except Exception as e:  # record unsupported options rather than skipping them
        return {"error": repr(e)}
    ids = enc["input_ids"]
    return {
        "input_ids": ids,
        "attention_mask": enc["attention_mask"],
        "tokens": tok.convert_ids_to_tokens(ids),
        "decoded": tok.decode(ids),
    }


def probe(name, revision):
    print(f"Probing {name}@{revision}", flush=True)
    files = {}
    for fname in ["tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "config.json"]:
        files[fname] = sha256_file(hf_hub_download(name, fname, revision=revision))
    with open(hf_hub_download(name, "config.json", revision=revision), encoding="utf-8") as f:
        model_config = json.load(f)

    tok = AutoTokenizer.from_pretrained(name, revision=revision)
    slow = AutoTokenizer.from_pretrained(name, revision=revision, use_fast=False)
    vocab = tok.get_vocab()

    return {
        "revision": revision,
        "file_sha256": files,
        "tokenizer_class": type(tok).__name__,
        "is_fast": tok.is_fast,
        "use_fast_false": {"class": type(slow).__name__, "is_fast": slow.is_fast},
        "len_tokenizer": len(tok),
        "tokenizer_vocab_size": tok.vocab_size,
        "config_vocab_size": model_config.get("vocab_size"),
        "config_tie_word_embeddings": model_config.get("tie_word_embeddings"),
        "config_dtype": model_config.get("torch_dtype", model_config.get("dtype")),
        "vocab_sha256": sha256_json(vocab),
        "special_tokens_map": tok.special_tokens_map,
        "bos_token": tok.bos_token,
        "eos_token": tok.eos_token,
        "pad_token": tok.pad_token,
        "pad_token_id": tok.pad_token_id,
        "all_special_ids": tok.all_special_ids,
        "added_tokens": {str(k): v.content for k, v in tok.added_tokens_decoder.items()},
        "padding_side": tok.padding_side,
        "truncation_side": tok.truncation_side,
        "split_special_tokens_default": getattr(tok, "split_special_tokens", None),
        "probes": {
            label: {"text": text, "modes": {m: encode(tok, text, kw) for m, kw in MODES.items()}}
            for label, text in FIXTURES
        },
    }, vocab


def main():
    results = {}
    vocabs = {}
    for name, rev in MODEL_REVISIONS.items():
        results[name], vocabs[name] = probe(name, rev)

    comparisons = []
    for a, b in itertools.combinations(results, 2):
        ra, rb = results[a], results[b]
        id_mismatches = [
            f"{label}/{mode}"
            for label in ra["probes"]
            for mode in MODES
            if ra["probes"][label]["modes"][mode] != rb["probes"][label]["modes"][mode]
        ]
        comparisons.append({
            "a": a,
            "b": b,
            "tokenizer_json_identical": ra["file_sha256"]["tokenizer.json"] == rb["file_sha256"]["tokenizer.json"],
            "vocab_identical": vocabs[a] == vocabs[b],
            "added_tokens_identical": ra["added_tokens"] == rb["added_tokens"],
            "config_vocab_size_identical": ra["config_vocab_size"] == rb["config_vocab_size"],
            "probe_mismatches": id_mismatches,
            "differing_special_tokens": {
                k: [ra[k], rb[k]] for k in ["bos_token", "eos_token", "pad_token"] if ra[k] != rb[k]
            },
        })

    # Within each tokenizer: does any mode differ from the proposed policy (add_special_tokens=False)?
    policy_deviations = {
        name: {
            label: [m for m in MODES if r["probes"][label]["modes"][m] != r["probes"][label]["modes"]["add_special_tokens_false"]]
            for label in r["probes"]
        }
        for name, r in results.items()
    }

    out = {
        "status": "provisional Task 1 measurement",
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "transformers": transformers.__version__,
            "tokenizers": tokenizers.__version__,
        },
        "modes": MODES,
        "tokenizers": results,
        "pairwise": comparisons,
        "modes_differing_from_add_special_tokens_false": policy_deviations,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    for c in comparisons:
        print(f"{c['a']} vs {c['b']}: tokenizer.json identical={c['tokenizer_json_identical']} "
              f"vocab identical={c['vocab_identical']} probe mismatches={len(c['probe_mismatches'])} "
              f"special-token differences={c['differing_special_tokens']}")
    for name, devs in policy_deviations.items():
        print(f"{name}: modes differing from add_special_tokens=False -> "
              + json.dumps({k: v for k, v in devs.items() if v}))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
