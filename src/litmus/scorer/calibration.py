"""Strict calibration lookup by exact scoring_config_hash (R1-PLAN §1.2).

R1-B1 only looks calibrations up; applying a threshold is R1-F's job.
"""
import json
import pathlib
from typing import Any, Dict, Optional


def default_calibrations_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[3] / "calibrations"


def find_calibration(config_hash: str,
                     calibrations_dir: Optional[pathlib.Path] = None
                     ) -> Optional[Dict[str, Any]]:
    """Return the calibration whose scoring_config_hash equals config_hash exactly."""
    directory = pathlib.Path(calibrations_dir or default_calibrations_dir())
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("scoring_config_hash") == config_hash:
            return data
    return None
