from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Modality(Enum):
    CONTAINER = "container"
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

class ExtractionStatus(Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"

class OriginResult(Enum):
    SUPPORTS_AI = "supports_ai"
    NO_SIGNAL = "no_signal"
    INCONCLUSIVE = "inconclusive"
    NOT_SUPPORTED = "not_supported"
    ERROR = "error"

@dataclass
class Calibration:
    scoring_config_hash: str
    dev_set_id: str
    alpha: float
    threshold_c: float
    n_dev_negatives: int
    created: str

@dataclass
class OriginEvidence:
    method_id: str
    method_version: str
    result: OriginResult
    raw_score: Optional[float] = None
    score_direction: Optional[str] = None
    calibration: Optional[Calibration] = None
    provenance: Optional[Dict[str, Any]] = None
    reasons: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

class QualityStatus(Enum):
    OBSERVED = "observed"
    NONE_FOUND = "none_found"
    NOT_SUPPORTED = "not_supported"
    ERROR = "error"


@dataclass
class QualityObservation:
    observer_id: str
    observer_version: str
    status: QualityStatus
    count: Optional[int] = None
    rate_per_100_words: Optional[float] = None
    spans: List[List[int]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.status, QualityStatus):
            try:
                self.status = QualityStatus(self.status)
            except ValueError:
                raise ValueError(f"Invalid status: {self.status}")

@dataclass
class Segment:
    segment_id: str
    parent_id: Optional[str]
    modality: Modality
    derivation: List[str]
    coords_in_parent: Optional[Any] = None
    local_frame: Optional[Any] = None
    content_sha256: str = ""
    extraction: Dict[str, Any] = field(
        default_factory=lambda: {"status": "skipped", "notes": []}
    )
    origin: List[OriginEvidence] = field(default_factory=list)
    quality: List[QualityObservation] = field(default_factory=list)

def to_json(obj):
    if isinstance(obj, Enum):
        return obj.value
    # str subclasses (e.g. torch's TorchVersion) carry a __dict__; keep the text
    if isinstance(obj, str):
        return str(obj)
    if isinstance(obj, list):
        return [to_json(i) for i in obj]
    if isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}
    if hasattr(obj, '__dict__'):
        return {k: to_json(v) for k, v in obj.__dict__.items()}
    return obj

def from_json(cls, data):
    if data is None:
        return None
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict for {cls.__name__}, got {type(data).__name__}")

    if hasattr(cls, '__annotations__'):
        fields = cls.__annotations__
        init_args = {}
        for name, type_hint in fields.items():
            if name not in data:
                # Only reject if not provided by default_factory or Optional
                # Note: simple check for R0.
                # In a real dataclass, we'd check for default values.
                # For these specific schemas, all are required except those with
                # Optional/default_factory.
                # We'll check if it's a list/dict with default_factory (usually is).
                # But we must reject if it's a core required field.
                # Let's explicitly list required fields for the main classes.
                required = {
                    Segment: {"segment_id", "parent_id", "modality", "derivation"},
                    OriginEvidence: {"method_id", "method_version", "result"},
                    Calibration: {
                        "scoring_config_hash", "dev_set_id", "alpha",
                        "threshold_c", "n_dev_negatives", "created"
                    },
                    QualityObservation: {"observer_id", "observer_version", "status"}
                }
                if cls in required and name in required[cls]:
                    raise KeyError(
                        f"Missing required field '{name}' for {cls.__name__}"
                    )
                continue

            val = data[name]

            # Enum validation
            if isinstance(type_hint, type) and issubclass(type_hint, Enum):
                try:
                    init_args[name] = type_hint(val)
                except ValueError:
                    raise ValueError(
                        f"Invalid enum value '{val}' for {name} "
                        f"(expected {type_hint.__name__})"
                    )
                continue

            # Nested types
            if type_hint == List[str]:
                init_args[name] = list(val) if val else []
            elif type_hint == List[OriginEvidence]:
                init_args[name] = [
                    from_json(OriginEvidence, i) for i in data.get(name, [])
                ]
            elif type_hint == List[QualityObservation]:
                init_args[name] = [
                    from_json(QualityObservation, i) for i in data.get(name, [])
                ]
            elif type_hint == Optional[Calibration]:
                init_args[name] = from_json(Calibration, val) if val else None
            else:
                init_args[name] = val
        return cls(**init_args)
    return data
