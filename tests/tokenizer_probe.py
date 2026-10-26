import torch
import json
import hashlib
from transformers import AutoTokenizer
from pathlib import Path

def get_tokenizer_config(tokenizer):
    # Extract tokenizer.json if possible from the cache
    # This is tricky as transformers hides the path. 
    # We'll use the vocab and special tokens as our primary evidence.
    return {
        "vocab_size": len(tokenizer),
        "special_tokens": {k: v for k, v in tokenizer.special_tokens_map.items()},
        "all_special_ids": tokenizer.all_special_ids
    }

def probe_tokenizer(name, revision, fixtures):
    print(f"Probing {name}@{revision}...")
    tok = AutoTokenizer.from_pretrained(name, revision=revision)
    
    results = {}
    for text, label in fixtures:
        # Probe 1: add_special_tokens=False
        ids_false = tok.encode(text, add_special_tokens=False)
        # Probe 2: add_special_tokens=True
        ids_true = tok.encode(text, add_special_tokens=True)
        # Probe 3: split_special_tokens=False
        ids_split_f = tok.encode(text, add_special_tokens=False, split_special_tokens=False)
        # Probe 4: split_special_tokens=True
        ids_split_t = tok.encode(text, add_special_tokens=False, split_special_tokens=True)
        
        results[label] = {
            "text": text,
            "ids_false": ids_false,
            "ids_true": ids_true,
            "ids_split_false": ids_split_f,
            "ids_split_true": ids_split_t,
            "tokens_false": tok.convert_ids_to_tokens(ids_false)
        }
    
    return {
        "config": get_tokenizer_config(tok),
        "probes": results
    }

if __name__ == "__main__":
    models = [
        ("Qwen/Qwen2.5-0.5B", "main"),
        ("Qwen/Qwen2.5-0.5B-Instruct", "main"),
        ("Qwen/Qwen2.5-1.5B", "main"),
        ("Qwen/Qwen2.5-1.5B-Instruct", "main"),
    ]
    
    fixtures = [
        ("The quick brown fox.", "ordinary"),
        ("Hello 🌍!", "unicode"),
        ("A​ B", "zero_width"),
        ("Tеst", "homoglyph"),
        ("Text with <|endoftext|> and <|im_end|>", "special_strings"),
    ]
    
    all_results = {}
    for name, rev in models:
        all_results[f"{name}@{rev}"] = probe_tokenizer(name, rev, fixtures)
    
    with open("eval/results/tokenizer_checks.json", "w") as f:
        json.dump(all_results, f, indent=2)
