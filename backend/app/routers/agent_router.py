from __future__ import annotations

import logging
import re
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.action_agent import ActionAgent
from app.models.enums import AgentActionStatus, AgentActionType, UserRole
from app.models.utilisateur import Utilisateur
from app.services.reschedule_service import (
    SimulationResult,
    apply_proposal,
    simulate_delay,
    simulate_reassignment,
)

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


class ActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    projet_id: UUID
    tache_id: UUID | None
    type: AgentActionType
    statut: AgentActionStatus
    justification: str
    payload: dict[str, Any]
    simulation_result: dict[str, Any] | None = None
    validation_status: str | None = None
    date_creation: datetime
    date_decision: datetime | None
    decideur_id: UUID | None
    decideur_nom: str | None = None


class ActionModify(BaseModel):
    strategy: AgentActionType
    delay_days: int | None = Field(default=None, ge=0)
    new_resource_id: UUID | None = None
    justification: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_parameters(self) -> "ActionModify":
        if self.strategy == AgentActionType.DECALAGE and self.delay_days is None:
            raise ValueError("delay_days est obligatoire pour un décalage")
        if self.strategy == AgentActionType.REAFFECTATION and self.new_resource_id is None:
            raise ValueError("new_resource_id est obligatoire pour une réaffectation")
        if self.strategy not in (
            AgentActionType.DECALAGE,
            AgentActionType.REAFFECTATION,
        ):
            raise ValueError("Type d'action non modifiable")
        return self


def _get_action(db: Session, action_id: UUID) -> ActionAgent:
    action = db.get(ActionAgent, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action introuvable")
    return action


def _authorize(action: ActionAgent, user: Utilisateur) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role != UserRole.CHEF_PROJET or action.projet.chef_id != user.id:
        raise HTTPException(status_code=403, detail="Permissions insuffisantes")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact(item)
            for key, item in value.items()
            if "motif" not in str(key).lower()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"maladie|congé|conge", "Absence", value, flags=re.IGNORECASE)
    return value


def _serialize(action: ActionAgent, user: Utilisateur) -> ActionRead:
    payload = action.payload or {}
    exposed_payload = payload if user.role == UserRole.ADMIN else _redact(payload)
    justification = action.justification if user.role == UserRole.ADMIN else _redact(action.justification)
    return ActionRead(
        id=action.id,
        projet_id=action.projet_id,
        tache_id=action.tache_id,
        type=action.type,
        statut=action.statut,
        justification=justification,
        payload=exposed_payload,
        simulation_result=exposed_payload.get("simulation_result"),
        validation_status=exposed_payload.get("validation_status"),
        date_creation=action.date_creation,
        date_decision=action.date_decision,
        decideur_id=action.decideur_id,
        decideur_nom=action.decideur.nom if action.decideur else None,
    )


@router.get("/actions", response_model=list[ActionRead])
def list_actions(
    statut: AgentActionStatus = Query(AgentActionStatus.EN_ATTENTE),
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(get_current_user),
) -> list[ActionRead]:
    query = select(ActionAgent).where(ActionAgent.statut == statut)
    if project_id is not None:
        query = query.where(ActionAgent.projet_id == project_id)
    if user.role != UserRole.ADMIN:
        if user.role != UserRole.CHEF_PROJET:
            raise HTTPException(status_code=403, detail="Permissions insuffisantes")
        query = query.where(ActionAgent.projet.has(chef_id=user.id))
    actions = list(db.scalars(query.order_by(ActionAgent.date_creation.desc())).all())
    return [_serialize(action, user) for action in actions]


@router.post("/actions/{action_id}/accept", response_model=ActionRead)
def accept_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(get_current_user),
) -> ActionRead:
    action = _get_action(db, action_id)
    _authorize(action, user)
    if action.statut != AgentActionStatus.EN_ATTENTE:
        raise HTTPException(status_code=409, detail="Cette action a déjà été décidée")
    try:
        accepted = apply_proposal(db, action_id, user.id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        detail = str(error)
        code = 409 if "planning modifié" in detail or "déjà" in detail else 422
        raise HTTPException(status_code=code, detail=detail) from error
    logger.info("Action agent %s acceptée par %s", accepted.id, user.id)
    return _serialize(accepted, user)


@router.post("/actions/{action_id}/reject", response_model=ActionRead)
def reject_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(get_current_user),
) -> ActionRead:
    action = _get_action(db, action_id)
    _authorize(action, user)
    if action.statut != AgentActionStatus.EN_ATTENTE:
        raise HTTPException(status_code=409, detail="Cette action a déjà été décidée")
    action.statut = AgentActionStatus.REJETEE
    action.date_decision = datetime.utcnow()
    action.decideur_id = user.id
    db.commit()
    db.refresh(action)
    logger.info("Action agent %s rejetée par %s", action.id, user.id)
    return _serialize(action, user)


@router.post("/actions/{action_id}/modify", response_model=ActionRead)
def modify_action(
    action_id: UUID,
    data: ActionModify,
    db: Session = Depends(get_db),
    user: Utilisateur = Depends(get_current_user),
) -> ActionRead:
    action = _get_action(db, action_id)
    _authorize(action, user)
    if action.statut != AgentActionStatus.EN_ATTENTE:
        raise HTTPException(status_code=409, detail="Cette action a déjà été décidée")
    if action.tache_id is None:
        raise HTTPException(status_code=422, detail="L'action ne référence aucune tâche")
    try:
        if data.strategy == AgentActionType.DECALAGE:
            simulation = simulate_delay(db, action.tache_id, data.delay_days or 0)
        else:
            if data.new_resource_id is None:
                raise HTTPException(
                    status_code=422,
                    detail="new_resource_id est obligatoire pour une réaffectation",
                )
            simulation = simulate_reassignment(
                db, action.tache_id, data.new_resource_id
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    action.type = data.strategy
    action.justification = data.justification or action.justification
    action.payload = {
        "params": {
            "delay_days": data.delay_days,
            "new_resource_id": str(data.new_resource_id) if data.new_resource_id else None,
        },
        "simulation_result": _simulation_payload(simulation),
        "planning_snapshot": {
            "task_start": action.tache.date_debut_prevue.isoformat(),
            "task_end": action.tache.date_fin_prevue.isoformat(),
            "project_end": action.projet.date_fin.isoformat(),
        },
    }
    db.commit()
    db.refresh(action)
    logger.info("Action agent %s modifiée par %s", action.id, user.id)
    return _serialize(action, user)


def _simulation_payload(result: SimulationResult) -> dict[str, Any]:
    return {
        "task_id": str(result.task_id),
        "ancienne_date_fin_tache": result.ancienne_date_fin_tache.isoformat(),
        "nouvelle_date_fin_tache": result.nouvelle_date_fin_tache.isoformat(),
        "ancienne_date_fin_projet": result.ancienne_date_fin_projet.isoformat(),
        "nouvelle_date_fin_projet": result.nouvelle_date_fin_projet.isoformat(),
        "retard_projet_jours": result.retard_projet_jours,
        "taches_nouvellement_critiques": [str(item) for item in result.taches_nouvellement_critiques],
        "nouveaux_conflits": _redact(result.nouveaux_conflits),
        "ressource_actuelle_id": str(result.ressource_actuelle_id) if result.ressource_actuelle_id else None,
        "nouvelle_ressource_id": str(result.nouvelle_ressource_id) if result.nouvelle_ressource_id else None,
        "reaffectation_possible": result.reaffectation_possible,
        "problemes": result.problemes,
        "ancienne_marge": result.ancienne_marge,
        "nouvelle_marge": result.nouvelle_marge,
    }
