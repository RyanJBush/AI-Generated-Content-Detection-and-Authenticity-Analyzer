"""Pinned R1 text-scorer configuration (Addendum A4; R1-PLAN §1.1–1.2).

Every value here enters the scoring_config_hash (see docs/interfaces.md).
Changing any of them invalidates every calibration.
"""

SCORER_VERSION = "r1b1-1"
FORMULA_ID = "binoculars_shiftednll_allposxent_v1"
SCORE_DIRECTION = "lower_means_more_machine"

OBSERVER_REPO = "Qwen/Qwen2.5-0.5B"
OBSERVER_COMMIT = "060db6499f32faf8b98477b0a26969ef7d8b9987"
OBSERVER_DIR = "Qwen2.5-0.5B"
PERFORMER_REPO = "Qwen/Qwen2.5-0.5B-Instruct"
PERFORMER_COMMIT = "7ae557604adf67be50417f59c2c2f167def9a775"
PERFORMER_DIR = "Qwen2.5-0.5B-Instruct"
# Identical in both repos (R1-A, eval/results/r1a_tokenizer_checks.json)
TOKENIZER_JSON_SHA256 = (
    "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539"
)

# Preprocessing policy (approved by Ryan for R1-B1)
PREPROCESSING_VERSION = "r1-text-v1"
ADD_SPECIAL_TOKENS = False
SPLIT_SPECIAL_TOKENS = True
TRUNCATION_SIDE = "right"
MAX_TOKENS = 512
MIN_TOKENS = 64

# Numerical policy (approved by Ryan for R1-B1)
WEIGHT_DTYPE = "float32"
REDUCTION_DTYPE = "float32"
ATTN_IMPLEMENTATION = "eager"
BATCH_SIZE = 1
ALLOW_TF32_MATMUL = False
ALLOW_TF32_CUDNN = False
FLOAT32_MATMUL_PRECISION = "highest"
DETERMINISTIC_ALGORITHMS = True
# Required by torch for deterministic cuBLAS; must be set before CUDA init
CUBLAS_WORKSPACE_CONFIG = ":4096:8"
