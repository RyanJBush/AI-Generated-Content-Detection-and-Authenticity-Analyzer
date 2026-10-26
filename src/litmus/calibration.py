"""Read-only calibration lookup for the CLI/app (contract: docs/interfaces.md §4). Codex writes the files."""
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

CALIBRATION_DIR = Path(__file__).resolve().parents[2] / "calibration"
FORMAT_VERSION = 1


@dataclass
class CalibrationStatus:
    valid: bool
    reason: str
    path: str
    t_strict: float | None = None
    t_primary: float | None = None
    artifact_sha256: str | None = None


def load_calibration(identity, directory=CALIBRATION_DIR):
    """Valid only if <directory>/<scoring_config_hash>.json exists and matches the current identity exactly."""
    path = Path(directory) / f"{identity['scoring_config_hash']}.json"
    shown = str(path)
    if not path.is_file():
        return CalibrationStatus(False, "no calibration file for this scoring configuration", shown)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()

    def invalid(reason):
        return CalibrationStatus(False, reason, shown, artifact_sha256=sha)

    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return invalid(f"calibration file is not valid JSON: {e}")
    if not isinstance(data, dict) or data.get("format_version") != FORMAT_VERSION:
        return invalid(f"calibration format_version must be {FORMAT_VERSION}")
    for key in ["scoring_config_hash", "scoring_identity_hash", "execution_profile_hash"]:
        if data.get(key) != identity[key]:
            return invalid(f"{key} in calibration file does not match the loaded scorer")
    try:
        detector = data["detectors"]["binoculars"]
        t_strict = detector["thresholds"]["fpr_0.01"]["threshold"]
        t_primary = detector["thresholds"]["fpr_0.05"]["threshold"]
    except (KeyError, TypeError):
        return invalid("calibration file lacks binoculars fpr_0.01/fpr_0.05 thresholds")
    if detector.get("direction") != "lower_is_machine":
        return invalid("binoculars direction must be lower_is_machine")
    if not all(isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) for t in (t_strict, t_primary)):
        return invalid("binoculars thresholds must be finite numbers")
    if t_strict > t_primary:
        return invalid("t_strict must not exceed t_primary")
    return CalibrationStatus(True, "valid", shown, float(t_strict), float(t_primary), sha)
