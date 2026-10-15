from datetime import date
from uuid import uuid4

from app.models.alerte import Alerte
from app.models.enums import AlertType, RiskLevel
from app.monitoring import job


def test_monitoring_without_anomaly_creates_no_alert(db_session, monkeypatch):
    monkeypatch.setattr(job, "_detect_delays", lambda db, today: 0)
    monkeypatch.setattr(job, "_detect_overallocations", lambda db, today: 0)
    monkeypatch.setattr(job, "_detect_schedule_slips", lambda db: 0)
    monkeypatch.setattr(job, "_detect_unhandled_conflicts", lambda db: [])

    assert job.run_monitoring_job(db_session, date(2026, 10, 14)) == 0
    assert db_session.query(Alerte).count() == 0


def test_unresolved_identical_alert_is_not_duplicated(db_session):
    project_id = uuid4()
    message = "Retard déterministe"

    first = job._create_alert(
        db_session, project_id, AlertType.RETARD, message, RiskLevel.MOYEN
    )
    second = job._create_alert(
        db_session, project_id, AlertType.RETARD, message, RiskLevel.MOYEN
    )

    assert first is not None
    assert second is None


def test_delay_and_overallocation_never_call_conflict_handler(db_session, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(job, "_detect_delays", lambda db, today: 1)
    monkeypatch.setattr(job, "_detect_overallocations", lambda db, today: 1)
    monkeypatch.setattr(job, "_detect_schedule_slips", lambda db: 0)
    monkeypatch.setattr(job, "_detect_unhandled_conflicts", lambda db: [])
    monkeypatch.setattr(
        job,
        "handle_unavailability_created",
        lambda unavailability_id: calls.append(str(unavailability_id)),
    )

    job.run_monitoring_job(db_session, date(2026, 10, 14))

    assert calls == []


def test_only_confirmed_conflict_calls_conflict_handler(db_session, monkeypatch):
    unavailability_id = uuid4()
    calls: list[str] = []
    monkeypatch.setattr(job, "_detect_delays", lambda db, today: 0)
    monkeypatch.setattr(job, "_detect_overallocations", lambda db, today: 0)
    monkeypatch.setattr(job, "_detect_schedule_slips", lambda db: 0)
    monkeypatch.setattr(job, "_detect_unhandled_conflicts", lambda db: [unavailability_id])
    monkeypatch.setattr(
        job,
        "handle_unavailability_created",
        lambda item_id: calls.append(str(item_id)),
    )

    job.run_monitoring_job(db_session, date(2026, 10, 14))

    assert calls == [str(unavailability_id)]
