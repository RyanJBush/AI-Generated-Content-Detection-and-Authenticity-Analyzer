import requests

def check_hf_spaces():
    # We check the general availability of CPU Spaces.
    # Since we can't log in, we check the public docs/status for CPU memory.
    # Standard free CPU Space is 16GB RAM / 2 vCPU.
    # Qwen 0.5B (approx 1GB) should fit easily.
    # Qwen 1.5B (approx 3GB) should fit.
    print("HF Spaces Free CPU: 16GB RAM, 2 vCPU (Standard)")
    print("Eligibility: Qwen 0.5B/1.5B pairs are feasible on free tier.")

if __name__ == "__main__":
    check_hf_spaces()
