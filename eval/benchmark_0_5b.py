import torch
import time
import json
import numpy as np
from transformers import AutoTokenizer, AutoModelForCausalLM
from pathlib import Path

def measure_runtime(model_name, tokenizer_name, texts, device="cuda"):
    print(f"Measuring {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
    model = AutoModelForCausalLM.from_pretrained(model_name).to(device).eval()
    
    # Warmup
    dummy_text = "Warmup text for GPU."
    inputs = tokenizer(dummy_text, return_tensors="pt").to(device)
    with torch.inference_mode():
        for _ in range(5):
            _ = model(**inputs)
    
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    
    results = []
    for text in texts:
        # Tokenize
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
        input_ids = inputs["input_ids"]
        attention_mask = inputs["attention_mask"]
        
        start_time = time.perf_counter()
        with torch.inference_mode():
            # Forward pass
            outputs = model(**inputs)
            logits = outputs.logits # [batch, seq, vocab]
            
            # full-vocabulary cross-entropy reduction
            # NLL = -log_softmax(logits)[target]
            # XENT = sum(exp(log_softmax(obs)) * -log_softmax(perf))
            # This benchmark measures the cost of these operations.
            
            # Simulating the Binoculars reduction cost:
            # Log-softmax is expensive.
            log_probs = torch.nn.functional.log_softmax(logits.float(), dim=-1)
            
            # Dummy reduction to simulate full-vocab XENT:
            # sum_{v} exp(O_v) * P_v
            # Here we just do a large matmul or sum to exercise the memory bandwidth
            _ = torch.sum(torch.exp(log_probs) * log_probs, dim=-1)
            
            torch.cuda.synchronize()
        end_time = time.perf_counter()
        
        results.append({
            "length": input_ids.shape[1],
            "time": end_time - start_time
        })
        
    peak_mem = torch.cuda.max_memory_allocated()
    reserved_mem = torch.cuda.max_memory_reserved()
    
    return results, peak_mem, reserved_mem

if __name__ == "__main__":
    model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    tokenizer_name = "Qwen/Qwen2.5-0.5B"
    
    # Synthetic texts of increasing length
    texts = [" ".join(["word"] * i) for i in [16, 64, 128, 256, 512]]
    
    results, peak, reserved = measure_runtime(model_name, tokenizer_name, texts)
    
    output = {
        "model": model_name,
        "results": results,
        "peak_memory": peak,
        "reserved_memory": reserved,
        "device": "cuda"
    }
    
    with open("eval/results/benchmark_0_5b.json", "w") as f:
        json.dump(output, f, indent=2)
