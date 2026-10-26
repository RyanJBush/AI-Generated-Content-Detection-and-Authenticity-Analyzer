# Pinned Model and Tokenizer Configuration

# Recommended Pair (to be finalized after Task 1)
# observer = "Qwen/Qwen2.5-0.5B"
# performer = "Qwen/Qwen2.5-0.5B-Instruct"

# Pinned Revisions (placeholder - to be updated after verification)
OBSERVER_REVISION = None
PERFORMER_REVISION = None

# Hub commit each candidate repo's `main` resolved to in the local HF cache on 2026-10-26.
# Pinned for tokenizer checks; the selected pair's revisions above remain unset until Task 1 review.
MODEL_REVISIONS = {
    "Qwen/Qwen2.5-0.5B": "060db6499f32faf8b98477b0a26969ef7d8b9987",
    "Qwen/Qwen2.5-0.5B-Instruct": "7ae557604adf67be50417f59c2c2f167def9a775",
    "Qwen/Qwen2.5-1.5B": "8faed761d45a263340a0528343f099c05c9a4323",
    "Qwen/Qwen2.5-1.5B-Instruct": "989aa7980e4cf806f80c7fef2b1adb7bc71aa306",
}

# Tokenization Settings
ADD_SPECIAL_TOKENS = False
PADDING_SIDE = "right"
TRUNCATION_SIDE = "right"
MAX_LENGTH = 512

# Numerical Settings
REDUCTION_DTYPE = "float32"
