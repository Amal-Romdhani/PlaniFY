from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.models.action_agent import ActionAgent
from app.models.alerte import Alerte
from app.models.enums import AgentActionStatus, AgentActionType, AlertType, RiskLevel
from app.models.tache import Tache
from app.services.critical_path_service import get_project_schedule
from app.services.resource_allocation_service import ResourceAllocationService
from app.services.reschedule_service import (
    SimulationResult,
    simulate_delay,
    simulate_reassignment,
)

logger = logging.getLogger(__name__)


class ResourceAvailabilityInput(BaseModel):
    resource_id: UUID
    start: date
    end: date


class DetectConflictsInput(ResourceAvailabilityInput):
    pass


class CriticalPathInput(BaseModel):
    project_id: UUID


class ReplacementCandidatesInput(BaseModel):
    task_id: UUID


class RescheduleTaskInput(BaseModel):
    task_id: UUID
    strategy: str = Field(pattern="^(DECALAGE|REAFFECTATION)$")
    delay_days: int | None = Field(default=None, ge=0)
    new_resource_id: UUID | None = None


class NotifyStakeholderInput(BaseModel):
    project_id: UUID
    task_id: UUID
    strategy: str = Field(pattern="^(DECALAGE|REAFFECTATION)$")
    params: dict[str, Any] = Field(default_factory=dict)
    justification: str = Field(min_length=1)

    @field_validator("params")
    @classmethod
    def params_are_rgpd_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        def walk(item: Any) -> bool:
            if isinstance(item, dict):
                return all(walk(key) and walk(child) for key, child in item.items())
            if isinstance(item, (list, tuple, set)):
                return all(walk(child) for child in item)
            return not any(
                term in str(item).lower() for term in ("motif", "maladie", "conge")
            )

        if not walk(value):
            raise ValueError("Les paramètres contiennent une donnée protégée")
        return value


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (UUID, date)):
        return str(value)
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value


def _simulation_output(result: SimulationResult) -> dict[str, Any]:
    return _json_value(result)


def _availability(db: Session, args: ResourceAvailabilityInput) -> dict[str, Any]:
    result = ResourceAllocationService(db).get_resource_availability(
        args.resource_id, args.start, args.end
    )
    return {
        "resource_id": result.resource_id,
        "days": result.days,
        "unavailable_periods": result.unavailable_periods,
    }


def _conflicts(db: Session, args: DetectConflictsInput) -> list[dict[str, Any]]:
    conflicts = ResourceAllocationService(db).detect_conflicts(
        args.resource_id, args.start, args.end
    )
    return [
        {
            "task_id": item.tache_id,
            "task_name": item.nom,
            "impacted_days": item.jours_impactes,
            "is_critical": item.est_critique,
            "margin": item.marge,
        }
        for item in conflicts
    ]


def _critical_path(db: Session, args: CriticalPathInput) -> dict[str, Any]:
    result = get_project_schedule(db, args.project_id)
    return {
        "critical_path": result.critical_path,
        "project_end_date": result.date_fin_projet,
        "total_duration": result.duree_totale,
        "tasks": {
            task_id: {
                "start": item.es,
                "end": item.ef,
                "margin": item.marge,
                "is_critical": item.est_critique,
            }
            for task_id, item in result.tasks.items()
        },
    }


def _replacement_candidates(
    db: Session, args: ReplacementCandidatesInput
) -> list[dict[str, Any]]:
    task = db.get(Tache, args.task_id)
    if task is None:
        raise ValueError("Tâche introuvable")
    result = ResourceAllocationService(db).find_replacement_candidates(
        args.task_id, (task.date_debut_prevue, task.date_fin_prevue)
    )
    return [_json_value(item) for item in result]


def _reschedule(db: Session, args: RescheduleTaskInput) -> dict[str, Any]:
    if args.strategy == "DECALAGE":
        if args.delay_days is None:
            raise ValueError("delay_days est obligatoire pour DECALAGE")
        return _simulation_output(simulate_delay(db, args.task_id, args.delay_days))
    if args.new_resource_id is None:
        raise ValueError("new_resource_id est obligatoire pour REAFFECTATION")
    return _simulation_output(
        simulate_reassignment(db, args.task_id, args.new_resource_id)
    )


def _notify(db: Session, args: NotifyStakeholderInput) -> dict[str, Any]:
    task = db.get(Tache, args.task_id)
    if task is None or task.projet_id != args.project_id:
        raise ValueError("La tâche n'appartient pas au projet")
    simulation_args = RescheduleTaskInput(
        task_id=args.task_id,
        strategy=args.strategy,
        delay_days=args.params.get("delay_days"),
        new_resource_id=args.params.get("new_resource_id"),
    )
    simulation = _reschedule(db, simulation_args)
    payload = {
        "params": args.params,
        "simulation_result": simulation,
    }
    action = ActionAgent(
        projet_id=args.project_id,
        tache_id=args.task_id,
        type=AgentActionType(args.strategy),
        justification=args.justification,
        payload=_json_value(payload),
        statut=AgentActionStatus.EN_ATTENTE,
    )
    db.add(action)
    db.flush()
    project = task.projet
    db.add(
        Alerte(
            projet_id=args.project_id,
            type=AlertType.RETARD,
            niveau_risque=RiskLevel.MOYEN,
            message=f"Une proposition {args.strategy} nécessite votre validation.",
        )
    )
    db.commit()
    db.refresh(action)
    return {
        "action_id": action.id,
        "status": action.statut,
        "payload": payload,
        "planning_modified": False,
    }


ToolHandler = Callable[[Session, BaseModel], Any]
ToolDefinition = tuple[type[BaseModel], ToolHandler]

TOOLS: dict[str, ToolDefinition] = {
    "getResourceAvailability": (ResourceAvailabilityInput, _availability),
    "detectConflicts": (DetectConflictsInput, _conflicts),
    "computeCriticalPath": (CriticalPathInput, _critical_path),
    "findReplacementCandidates": (ReplacementCandidatesInput, _replacement_candidates),
    "rescheduleTask": (RescheduleTaskInput, _reschedule),
    "notifyStakeholder": (NotifyStakeholderInput, _notify),
}


def anthropic_tools() -> list[dict[str, Any]]:
    """Produit les définitions compatibles avec l'API Anthropic."""

    return [
        {
            "name": name,
            "description": f"Outil déterministe PlaniFY: {name}",
            "input_schema": schema.model_json_schema(),
        }
        for name, (schema, _) in TOOLS.items()
    ]


def execute_tool(name: str, args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Valide, journalise et exécute un outil sans laisser remonter d'exception."""

    try:
        schema, handler = TOOLS[name]
        validated = schema.model_validate(args)
        logger.info("Agent tool call: %s", name)
        result = _json_value(handler(db, validated))
        json.dumps(result)
        return result
    except Exception as error:
        logger.exception("Agent tool failed: %s", name)
        return {"error": str(error)}
