import torch
import json
import time
from transformers import AutoTokenizer, AutoModelForCausalLM

def measure_drift(text, model_name, tokenizer_name, dtype):
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=dtype).to("cuda").eval()
    
    inputs = tokenizer(text, return_tensors="pt").to("cuda")
    
    with torch.inference_mode():
        outputs = model(**inputs)
        logits = outputs.logits.float() # Ensure reduction in float32
        
        # Simulated Binoculars calculation
        log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
        nll = -log_probs[0, :-1, inputs["input_ids"][0, 1:]].mean().item()
        xent = torch.sum(torch.exp(log_probs) * log_probs, dim=-1).mean().item()
        b_score = nll / xent if xent != 0 else float('inf')
        
    return {"nll": nll, "xent": xent, "b": b_score}

if __name__ == "__main__":
    pilot_texts = ["The quick brown fox jumps over the lazy dog.", "Artificial intelligence is transforming the world."]
    model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    tokenizer_name = "Qwen/Qwen2.5-0.5B"
    
    dtypes = {"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}
    results = {}
    
    for text in pilot_texts:
        text_res = {}
        for label, dtype in dtypes.items():
            text_res[label] = measure_drift(text, model_name, tokenizer_name, dtype)
        results[text] = text_res
        
    with open("eval/results/runtime_drift.json", "w") as f:
        json.dump(results, f, indent=2)
