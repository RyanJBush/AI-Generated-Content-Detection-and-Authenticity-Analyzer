"""Acquire only the approved pinned RAID train.csv; no preprocessing/scoring."""

import argparse
from pathlib import Path

from litmus.data_prep.acquisition import acquire

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    arguments = parser.parse_args()
    acquire(
        Path(__file__).resolve().parents[1], preflight_only=arguments.preflight_only
    )
