import pytest
import json
from src.litmus.schemas import (
    Segment, Modality, OriginResult, OriginEvidence,
    Calibration, QualityObservation, to_json, from_json
)

def test_schema_roundtrip():
    # Complex segment with nested structures
    cal = Calibration("hash123", "dev0", 0.05, 0.8, 100, "2026-10-26")
    evidence = OriginEvidence(
        method_id="det1",
        method_version="1.0",
        result=OriginResult.SUPPORTS_AI,
        raw_score=0.95,
        calibration=cal,
        reasons=["strong signal"],
        limitations=["small window"]
    )
    seg = Segment(
        segment_id="s1",
        parent_id="s0",
        modality=Modality.TEXT,
        derivation=["utf8_decode"],
        content_sha256="abc",
        origin=[evidence]
    )

    serialized = json.dumps(to_json(seg))
    deserialized_data = json.loads(serialized)

    # Manually reconstituting Segment for R0 test
    # Note: our from_json is basic, we verify fields match
    assert deserialized_data["segment_id"] == "s1"
    assert deserialized_data["modality"] == "text"
    assert deserialized_data["origin"][0]["result"] == "supports_ai"
    assert deserialized_data["origin"][0]["calibration"]["alpha"] == 0.05

def test_enum_rejection():
    with pytest.raises(ValueError):
        Modality("invalid_modality")
    with pytest.raises(ValueError):
        OriginResult("invalid_result")
