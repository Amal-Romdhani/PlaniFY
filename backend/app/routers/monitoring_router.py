from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alerte import Alerte
from app.models.enums import AlertType, RiskLevel, UserRole
from app.models.utilisateur import Utilisateur
from app.monitoring.job import run_monitoring_job

router = APIRouter(tags=["monitoring"])


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    projet_id: UUID | None
    type: AlertType
    niveau_risque: RiskLevel
    message: str
    date_creation: datetime
    resolue: bool


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    project_id: UUID | None = Query(default=None),
    include_resolved: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(get_current_user),
) -> list[Alerte]:
    query = select(Alerte)
    if not include_resolved:
        query = query.where(Alerte.resolue.is_(False))
    if project_id is not None:
        query = query.where(Alerte.projet_id == project_id)
    if user.role != UserRole.ADMIN:
        if user.role != UserRole.CHEF_PROJET:
            raise HTTPException(status_code=403, detail="Permissions insuffisantes")
        query = query.where(Alerte.projet.has(chef_id=user.id))
    return list(db.scalars(query.order_by(Alerte.date_creation.desc())).all())


@router.post("/alerts/{alert_id}/resolve", response_model=AlertRead)
def resolve_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(get_current_user),
) -> Alerte:
    alert = db.get(Alerte, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    if user.role != UserRole.ADMIN and (
        user.role != UserRole.CHEF_PROJET
        or alert.projet is None
        or alert.projet.chef_id != user.id
    ):
        raise HTTPException(status_code=403, detail="Permissions insuffisantes")
    alert.resolue = True
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/monitoring/run", response_model=dict[str, int])
def run_monitoring(
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(get_current_user),
) -> dict[str, int]:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Seul un administrateur peut lancer le monitoring")
    return {"alertes_creees": run_monitoring_job(db)}
