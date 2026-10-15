from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.trigger import handle_unavailability_created
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.action_agent import ActionAgent
from app.models.affectation import Affectation
from app.models.alerte import Alerte
from app.models.enums import AgentActionStatus, AlertType, RiskLevel, TaskStatus
from app.models.indisponibilite import Indisponibilite
from app.models.projet import Projet
from app.models.ressource import Ressource
from app.models.tache import Tache
from app.services.critical_path_service import WorkCalendar, recompute_project_schedule
from app.services.resource_allocation_service import ResourceAllocationService

logger = logging.getLogger(__name__)


def _working_days(start: date, end: date) -> int:
    if end < start:
        return 0
    return sum(
        (start + timedelta(days=offset)).weekday() < 5
        for offset in range((end - start).days + 1)
    )


def _create_alert(
    db: Session,
    project_id: UUID,
    alert_type: AlertType,
    message: str,
    level: RiskLevel,
) -> Alerte | None:
    existing = db.scalar(
        select(Alerte.id).where(
            Alerte.projet_id == project_id,
            Alerte.type == alert_type,
            Alerte.message == message,
            Alerte.resolue.is_(False),
        )
    )
    pending_duplicate = any(
        isinstance(item, Alerte)
        and item.projet_id == project_id
        and item.type == alert_type
        and item.message == message
        and item.resolue is not True
        for item in db.new
    )
    if existing is not None or pending_duplicate:
        return None
    alert = Alerte(
        projet_id=project_id,
        type=alert_type,
        niveau_risque=level,
        message=message,
    )
    db.add(alert)
    return alert


def _detect_delays(db: Session, today: date) -> int:
    created = 0
    for task in db.scalars(select(Tache)).all():
        if task.statut == TaskStatus.TERMINEE or task.duree <= 0:
            continue
        elapsed = _working_days(task.date_debut_prevue, min(today, task.date_fin_prevue))
        theoretical = min(100.0, elapsed / task.duree * 100)
        if today > task.date_debut_prevue and task.avancement < theoretical:
            message = f"Retard de la tâche {task.id}: avancement inférieur au planning théorique"
            if _create_alert(db, task.projet_id, AlertType.RETARD, message, RiskLevel.MOYEN):
                created += 1
    return created


def _detect_overallocations(db: Session, today: date) -> int:
    created = 0
    end = today + timedelta(days=27)
    for resource in db.scalars(select(Ressource)).all():
        periods = ResourceAllocationService(db).detect_overallocation(resource.id, today, end)
        for period in periods:
            message = (
                f"Sur-allocation de la ressource {resource.id} "
                f"du {period.date_debut.isoformat()} au {period.date_fin.isoformat()}"
            )
            project_ids = set(
                db.scalars(
                    select(Tache.projet_id)
                    .join(Affectation, Affectation.tache_id == Tache.id)
                    .where(Affectation.ressource_id == resource.id)
                ).all()
            )
            for project_id in project_ids:
                if _create_alert(db, project_id, AlertType.SURALLOCATION, message, RiskLevel.ELEVE):
                    created += 1
    return created


def _detect_schedule_slips(db: Session) -> int:
    created = 0
    for project in db.scalars(select(Projet)).all():
        before = project.date_fin
        recompute_project_schedule(db, project.id)
        if project.date_fin > before:
            message = (
                f"Glissement de la date de fin du projet {project.id}: "
                f"{before.isoformat()} -> {project.date_fin.isoformat()}"
            )
            if _create_alert(db, project.id, AlertType.RETARD, message, RiskLevel.ELEVE):
                created += 1
    return created


def _detect_unhandled_conflicts(db: Session) -> list[UUID]:
    unavailability_ids: list[UUID] = []
    service = ResourceAllocationService(db)
    for item in db.scalars(select(Indisponibilite)).all():
        conflicts = service.detect_conflicts(item.ressource_id, item.date_debut, item.date_fin)
        if not conflicts:
            continue
        conflict_task_ids = {conflict.tache_id for conflict in conflicts}
        handled = db.scalar(
            select(ActionAgent.id).where(
                ActionAgent.tache_id.in_(conflict_task_ids),
                ActionAgent.statut.in_(
                    (AgentActionStatus.EN_ATTENTE, AgentActionStatus.ACCEPTEE)
                ),
            )
        )
        if handled is None:
            unavailability_ids.append(item.id)
    return unavailability_ids


def run_monitoring_job(
    db: Session,
    today: date | None = None,
    conflict_handler: Callable[[UUID], None] | None = None,
) -> int:
    """Exécute les contrôles déterministes et retourne le nombre d'alertes créées."""

    current_day = today or date.today()
    conflict_handler = conflict_handler or handle_unavailability_created
    created = _detect_delays(db, current_day)
    created += _detect_overallocations(db, current_day)
    created += _detect_schedule_slips(db)
    db.flush()
    for unavailability_id in _detect_unhandled_conflicts(db):
        conflict_handler(unavailability_id)
    db.commit()
    return created


def run_scheduled_monitoring() -> None:
    """Point d'entrée APScheduler avec une session indépendante."""

    db = SessionLocal()
    try:
        run_monitoring_job(db)
    except Exception:
        db.rollback()
        logger.exception("Échec du monitoring planifié")
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    """Construit le scheduler configuré selon Settings."""

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_scheduled_monitoring,
        trigger="interval",
        minutes=settings.monitoring_interval_minutes,
        id="planify-monitoring",
        replace_existing=True,
    )
    return scheduler
