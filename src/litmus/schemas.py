from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union, Any, Dict
import json

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

@dataclass
class QualityObservation:
    observer_id: str
    observer_version: str
    status: str # "observed" | "none_found" | "not_supported" | "error"
    count: Optional[int] = None
    rate_per_100_words: Optional[float] = None
    spans: List[List[int]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

@dataclass
class Segment:
    segment_id: str
    parent_id: Optional[str]
    modality: Modality
    derivation: List[str]
    coords_in_parent: Optional[Any] = None
    local_frame: Optional[Any] = None
    content_sha256: str = ""
    extraction: Dict[str, Any] = field(default_factory=lambda: {"status": "skipped", "notes": []})
    origin: List[OriginEvidence] = field(default_factory=list)
    quality: List[QualityObservation] = field(default_factory=list)

def to_json(obj):
    if isinstance(obj, Enum):
        return obj.value
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
    if cls == List:
        return [from_json(Any, i) for i in data]
    if hasattr(cls, '__annotations__'):
        # Handle dataclasses
        fields = cls.__annotations__
        init_args = {}
        for name, type_hint in fields.items():
            val = data.get(name)
            # Basic type mapping for R0
            if type_hint == List[str]:
                init_args[name] = list(val) if val else []
            elif type_hint == List[OriginEvidence]:
                init_args[name] = [from_json(OriginEvidence, i) for i in data.get(name, [])]
            elif type_hint == List[QualityObservation]:
                init_args[name] = [from_json(QualityObservation, i) for i in data.get(name, [])]
            elif type_hint == Modality:
                init_args[name] = Modality(val)
            elif type_hint == OriginResult:
                init_args[name] = OriginResult(val)
            elif type_hint == Optional[Calibration]:
                init_args[name] = from_json(Calibration, val) if val else None
            else:
                init_args[name] = val
        return cls(**init_args)
    return data
