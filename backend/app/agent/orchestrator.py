from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import anthropic_tools, execute_tool
from app.core.config import settings
from app.models.action_agent import ActionAgent
from app.models.affectation import Affectation
from app.models.enums import AgentActionStatus, AgentActionType
from app.models.indisponibilite import Indisponibilite
from app.models.tache import Tache

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Interface minimale permettant de remplacer Claude dans les tests."""

    def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        ...


class AnthropicLLMClient:
    """Adaptateur du SDK Anthropic."""

    def __init__(self) -> None:
        from anthropic import Anthropic

        self.client = Anthropic(api_key=settings.anthropic_api_key)

    def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return self.client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1200,
            system=system,
            messages=messages,
            tools=tools,
        )


@dataclass
class AgentRunResult:
    """Résultat traçable d'une exécution agent."""

    final_response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    actions_created: list[ActionAgent] = field(default_factory=list)


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _content_blocks(response: Any) -> list[Any]:
    return list(_get(response, "content", []) or [])


def _block_json(block: Any) -> dict[str, Any]:
    if isinstance(block, dict):
        return block
    result: dict[str, Any] = {}
    for key in ("type", "id", "name", "input", "text"):
        value = _get(block, key)
        if value is not None:
            result[key] = value
    return result


def _text(response: Any) -> str:
    return "\n".join(
        str(_get(block, "text", ""))
        for block in _content_blocks(response)
        if _get(block, "type") == "text"
    ).strip()


def _create_alert_action(
    db: Session,
    project_id: UUID,
    task_id: UUID | None,
    message: str,
) -> ActionAgent:
    action = ActionAgent(
        projet_id=project_id,
        tache_id=task_id,
        type=AgentActionType.ALERTE,
        justification=message,
        payload={"message": message},
        statut=AgentActionStatus.EN_ATTENTE,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


class AgentOrchestrator:
    """Exécute une boucle ReAct bornée et sans écriture de planning."""

    def __init__(self, llm_client: LLMClient | None = None, max_iterations: int = 8) -> None:
        self.llm_client = llm_client or AnthropicLLMClient()
        self.max_iterations = max_iterations

    def _initial_context(
        self, db: Session, unavailability_id: UUID
    ) -> tuple[dict[str, Any], UUID, UUID | None]:
        item = db.get(Indisponibilite, unavailability_id)
        if item is None:
            raise ValueError("Indisponibilité introuvable")
        task = db.scalar(
            select(Tache)
            .join(Affectation, Affectation.tache_id == Tache.id)
            .where(
                Affectation.ressource_id == item.ressource_id,
                Tache.date_debut_prevue <= item.date_fin,
                Tache.date_fin_prevue >= item.date_debut,
            )
            .order_by(Tache.projet_id, Tache.id)
        )
        project_id = task.projet_id if task is not None else None
        context = {
            "unavailability_id": str(unavailability_id),
            "resource_id": str(item.ressource_id),
            "start": item.date_debut.isoformat(),
            "end": item.date_fin.isoformat(),
            "project_id": str(project_id) if project_id else None,
        }
        if project_id is None:
            raise ValueError("Aucun projet affecté à cette ressource")
        return context, project_id, task.id if task else None

    def run(self, db: Session, unavailability_id: UUID) -> AgentRunResult:
        context, project_id, task_id = self._initial_context(db, unavailability_id)
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    "Analyse cette indisponibilité avec ce contexte JSON. "
                    "Utilise obligatoirement les outils selon la procédure.\n"
                    f"{context}"
                ),
            }
        ]
        tool_calls: list[dict[str, Any]] = []
        tool_results: list[dict[str, Any]] = []
        actions: list[ActionAgent] = []

        try:
            for _ in range(self.max_iterations):
                response = self.llm_client.create_message(
                    SYSTEM_PROMPT, messages, anthropic_tools()
                )
                blocks = _content_blocks(response)
                messages.append(
                    {"role": "assistant", "content": [_block_json(block) for block in blocks]}
                )
                if _get(response, "stop_reason") == "end_turn":
                    return AgentRunResult(_text(response), tool_calls, tool_results, actions)
                uses = [block for block in blocks if _get(block, "type") == "tool_use"]
                if not uses:
                    return AgentRunResult(_text(response), tool_calls, tool_results, actions)
                results = []
                for block in uses:
                    name = _get(block, "name")
                    arguments = _get(block, "input", {})
                    result = execute_tool(name, arguments, db)
                    call = {"id": _get(block, "id"), "name": name, "input": arguments}
                    tool_calls.append(call)
                    tool_results.append({"tool_use_id": _get(block, "id"), "name": name, "result": result})
                    action_id = result.get("action_id") if isinstance(result, dict) else None
                    if action_id:
                        action = db.get(ActionAgent, UUID(str(action_id)))
                        if action is not None:
                            actions.append(action)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": _get(block, "id"),
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                messages.append({"role": "user", "content": results})
            message = "L'analyse automatique a atteint sa limite; validation humaine requise."
            actions.append(_create_alert_action(db, project_id, task_id, message))
            return AgentRunResult(message, tool_calls, tool_results, actions)
        except Exception:
            logger.exception("Erreur pendant l'exécution de l'agent")
            message = "L'analyse automatique est indisponible; validation humaine requise."
            actions.append(_create_alert_action(db, project_id, task_id, message))
            return AgentRunResult(message, tool_calls, tool_results, actions)
