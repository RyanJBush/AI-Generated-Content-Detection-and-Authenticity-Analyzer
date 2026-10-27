
import pytest

from src.litmus.schemas import (
    Calibration,
    Modality,
    OriginEvidence,
    OriginResult,
    QualityObservation,
    Segment,
    from_json,
    to_json,
)


def test_schema_full_roundtrip():
    # Complex segment with nested structures
    cal = Calibration("hash123", "dev0", 0.05, 0.8, 100, "2026-10-26")
    evidence = OriginEvidence(
        method_id="det1",
        method_version="1.0",
        result=OriginResult.SUPPORTS_AI,
        raw_score=0.95,
        calibration=cal,
        details={
            "scored_window": {
                "tokens_total": 100, "tokens_scored": 50,
                "truncated": True, "scored_char_range": [0, 500]
            }
        },
        reasons=["strong signal"],
        limitations=["small window"]
    )
    obs = QualityObservation(
        observer_id="obs1",
        observer_version="1.0",
        status="observed",
        count=5,
        spans=[[0, 10], [20, 30]]
    )
    seg = Segment(
        segment_id="s1",
        parent_id="s0",
        modality=Modality.TEXT,
        derivation=["utf8_decode"],
        content_sha256="abc",
        origin=[evidence],
        quality=[obs]
    )

    # to_json -> from_json -> equality
    serialized = to_json(seg)
    deserialized = from_json(Segment, serialized)
    assert deserialized == seg

def test_schema_rejection_missing_fields():
    # Segment missing modality
    with pytest.raises(KeyError, match="Missing required field 'modality'"):
        from_json(Segment, {"segment_id": "s1", "parent_id": None, "derivation": []})

    # OriginEvidence missing result
    with pytest.raises(KeyError, match="Missing required field 'result'"):
        from_json(OriginEvidence, {"method_id": "m1", "method_version": "1.0"})

    # Calibration missing alpha
    with pytest.raises(KeyError, match="Missing required field 'alpha'"):
        from_json(
            Calibration,
            {
                "scoring_config_hash": "h",
                "dev_set_id": "d",
                "threshold_c": 0.1,
                "n_dev_negatives": 10,
                "created": "date",
            }
        )

def test_schema_rejection_invalid_enums():
    # Invalid Modality
    with pytest.raises(ValueError, match="Invalid enum value 'invalid' for modality"):
        from_json(
            Segment,
            {
                "segment_id": "s1",
                "parent_id": None,
                "modality": "invalid",
                "derivation": [],
            }
        )

    # Invalid OriginResult
    with pytest.raises(ValueError, match="Invalid enum value 'invalid' for result"):
        from_json(
            OriginEvidence,
            {"method_id": "m1", "method_version": "1.0", "result": "invalid"}
        )

    # Invalid QualityStatus
    with pytest.raises(ValueError, match="Invalid enum value 'invalid' for status"):
        from_json(
            QualityObservation,
            {"observer_id": "o1", "observer_version": "1.0", "status": "invalid"}
        )
