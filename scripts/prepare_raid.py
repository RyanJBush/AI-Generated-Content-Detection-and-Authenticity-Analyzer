"""R1-E preparation only; approved constants, no scoring or model weights."""

import argparse
from pathlib import Path

from litmus.data_prep.acquisition import write_json
from litmus.data_prep.guards import preparation_guards
from litmus.data_prep.pipeline import prepare
from litmus.data_prep.text import load_local_tokenizer

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, choices=("primary", "repeat"))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    with preparation_guards() as attempts:
        tokenizer, identity = load_local_tokenizer(repo)
        prepare(repo, args.run_id, tokenizer, identity)
    write_json(repo / "eval/results" / f"r1e_{args.run_id}_guards.json", attempts)
