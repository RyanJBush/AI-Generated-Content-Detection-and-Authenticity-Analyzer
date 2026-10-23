import torch
from transformers import AutoTokenizer
import json
import hashlib

def get_sha256(file_path):
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def test_tokenizer_identical():
    pairs = [
        ("Qwen/Qwen2.5-0.5B", "Qwen/Qwen2.5-0.5B-Instruct"),
        ("Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-1.5B-Instruct"),
    ]
    
    for obs_name, perf_name in pairs:
        print(f"\nChecking pair: {obs_name} / {perf_name}")
        obs_tok = AutoTokenizer.from_pretrained(obs_name)
        perf_tok = AutoTokenizer.from_pretrained(perf_name)
        
        # 1. Check tokenizer.json identity (if available)
        # Note: AutoTokenizer doesn't provide the local path easily, we'd need to find it in cache.
        # As a proxy, we check vocab size and special tokens.
        print(f"Vocab sizes: Obs={obs_tok.vocab_size}, Perf={perf_tok.vocab_size}")
        assert obs_tok.vocab_size == perf_tok.vocab_size, f"Vocab size mismatch for {obs_name}/{perf_name}"
        
        # 2. Identical IDs on fixtures
        fixtures = [
            "The quick brown fox jumps over the lazy dog.",
            "Hello world! 🌍",
            "A​ B", # Zero-width space
            "Tеst", # Cyrillic 'е' (homoglyph)
        ]
        
        for text in fixtures:
            obs_ids = obs_tok.encode(text, add_special_tokens=False)
            perf_ids = perf_tok.encode(text, add_special_tokens=False)
            assert obs_ids == perf_ids, f"ID mismatch for text '{text}' in {obs_name}/{perf_name}"
        
        # 3. add_special_tokens True vs False
        text = "Test special tokens"
        ids_true = obs_tok.encode(text, add_special_tokens=True)
        ids_false = obs_tok.encode(text, add_special_tokens=False)
        print(f"add_special_tokens=True: {ids_true}")
        print(f"add_special_tokens=False: {ids_false}")
        # Record results without asserting (policy decision)

        # 4. Literal special tokens in raw text
        special_strings = ["<|endoftext|>", "<|im_end|>", "<|im_start|>"]
        for s in special_strings:
            ids_raw = obs_tok.encode(s, add_special_tokens=False)
            ids_split = obs_tok.encode(s, add_special_tokens=False, split_special_tokens=True)
            print(f"Special string '{s}': Raw={ids_raw}, Split={ids_split}")

if __name__ == "__main__":
    test_tokenizer_identical()
