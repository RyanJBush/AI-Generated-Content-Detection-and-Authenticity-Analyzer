import pytest

from litmus.schemas import QualityObservation, QualityStatus, from_json, to_json


def test_quality_observation_accepts_valid_statuses():
    for status_val in ["observed", "none_found", "not_supported", "error"]:
        obs = QualityObservation("obs1", "1.0", status_val)
        assert obs.status is QualityStatus(status_val)

        data = {"observer_id": "obs1", "observer_version": "1.0", "status": status_val}
        restored = from_json(QualityObservation, data)
        assert restored.status is QualityStatus(status_val)
        assert to_json(restored)["status"] == status_val


def test_quality_observation_rejects_invented_status_direct():
    with pytest.raises(ValueError, match="Invalid status"):
        QualityObservation("obs1", "1.0", "invented")


def test_quality_observation_rejects_invented_status_from_json():
    data = {"observer_id": "obs1", "observer_version": "1.0", "status": "invented"}
    with pytest.raises(ValueError, match="Invalid enum value 'invented' for status"):
        from_json(QualityObservation, data)
