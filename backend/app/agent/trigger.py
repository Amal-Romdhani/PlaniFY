from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.alerte import Alerte
from app.models.enums import AlertType, RiskLevel
from app.models.indisponibilite import Indisponibilite
from app.models.tache import Tache
from app.services.resource_allocation_service import ResourceAllocationService
from app.agent.orchestrator import AgentOrchestrator


def handle_unavailability_created(unavailability_id: UUID) -> None:
    """Crée les alertes de conflit après la déclaration d'une absence."""

    db = SessionLocal()
    try:
        item = db.get(Indisponibilite, unavailability_id)
        if item is None:
            return
        conflicts = ResourceAllocationService(db).detect_conflicts(
            item.ressource_id, item.date_debut, item.date_fin
        )
        project_ids = {
            task.projet_id
            for task in db.scalars(
                select(Tache).where(Tache.id.in_([conflict.tache_id for conflict in conflicts]))
            ).all()
        }
        for project_id in project_ids:
            already_exists = db.scalar(
                select(Alerte.id).where(
                    Alerte.projet_id == project_id,
                    Alerte.type == AlertType.CONFLIT_INDISPONIBILITE,
                    Alerte.resolue.is_(False),
                    Alerte.message.contains(str(unavailability_id)),
                )
            )
            if already_exists is None:
                db.add(
                    Alerte(
                        projet_id=project_id,
                        type=AlertType.CONFLIT_INDISPONIBILITE,
                        niveau_risque=RiskLevel.ELEVE,
                        message=f"Conflit d'indisponibilité détecté ({unavailability_id})",
                    )
                )
        if conflicts:
                AgentOrchestrator().run(db, unavailability_id)
        db.commit()
    finally:
        db.close()
