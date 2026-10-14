from datetime import date
from uuid import uuid4

from app.agent.orchestrator import AgentOrchestrator
from app.agent import trigger
from app.models.affectation import Affectation
from app.models.enums import (
    AgentActionStatus,
    ProjectStatus,
    ResourceType,
    TaskStatus,
    UnavailabilityReason,
    UserRole,
)
from app.models.indisponibilite import Indisponibilite
from app.models.projet import Projet
from app.models.ressource import Ressource
from app.models.tache import Tache
from app.models.utilisateur import Utilisateur


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def create_message(self, system, messages, tools):
        self.calls.append((system, messages, tools))
        return next(self.responses)


def _block(name, number, **input_data):
    return {
        "id": f"tool-{number}",
        "type": "tool_use",
        "name": name,
        "input": input_data,
    }


def _fixture(db_session):
    user = Utilisateur(
        nom="Chef agent",
        email=f"{uuid4()}@example.com",
        mot_de_passe_hash="hash",
        role=UserRole.CHEF_PROJET,
    )
    project = Projet(
        nom="Projet agent",
        date_debut=date(2026, 1, 5),
        date_fin=date(2026, 1, 30),
        statut=ProjectStatus.PLANIFIE,
        chef=user,
    )
    resource = Ressource(
        nom="Ressource agent",
        type=ResourceType.HUMAINE,
        charge_max=8,
        utilisateur=user,
    )
    task = Tache(
        projet=project,
        nom="Tâche agent",
        duree=3,
        date_debut_prevue=date(2026, 1, 5),
        date_fin_prevue=date(2026, 1, 7),
        statut=TaskStatus.A_FAIRE,
    )
    assignment = Affectation(ressource=resource, tache=task, charge_allouee=2)
    absence = Indisponibilite(
        ressource=resource,
        date_debut=date(2026, 1, 6),
        date_fin=date(2026, 1, 6),
        motif=UnavailabilityReason.CONGE,
    )
    db_session.add_all([user, project, resource, task, assignment, absence])
    db_session.flush()
    return project, task, absence


def test_react_order_and_no_planning_write(db_session, monkeypatch):
    project, task, absence = _fixture(db_session)
    responses = [
        {"stop_reason": "tool_use", "content": [_block("getResourceAvailability", 1, resource_id=str(uuid4()), start="2026-01-06", end="2026-01-06")]},
        {"stop_reason": "tool_use", "content": [_block("detectConflicts", 2, resource_id=str(uuid4()), start="2026-01-06", end="2026-01-06")]},
        {"stop_reason": "tool_use", "content": [_block("computeCriticalPath", 3, project_id=str(project.id))]},
        {"stop_reason": "tool_use", "content": [_block("findReplacementCandidates", 4, task_id=str(task.id))]},
        {"stop_reason": "tool_use", "content": [_block("rescheduleTask", 5, task_id=str(task.id), strategy="DECALAGE", delay_days=1)]},
        {"stop_reason": "tool_use", "content": [_block("notifyStakeholder", 6, project_id=str(project.id), task_id=str(task.id), strategy="DECALAGE", params={"delay_days": 1}, justification="Proposition")]},
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Proposition soumise."}]},
    ]
    fake = FakeLLMClient(responses)
    monkeypatch.setattr(
        "app.agent.orchestrator.execute_tool",
        lambda name, args, db: {"action_id": str(uuid4())}
        if name == "notifyStakeholder"
        else [],
    )
    before = (task.date_debut_prevue, task.date_fin_prevue)

    result = AgentOrchestrator(fake).run(db_session, absence.id)

    assert [call["name"] for call in result.tool_calls] == [
        "getResourceAvailability",
        "detectConflicts",
        "computeCriticalPath",
        "findReplacementCandidates",
        "rescheduleTask",
        "notifyStakeholder",
    ]
    db_session.refresh(task)
    assert (task.date_debut_prevue, task.date_fin_prevue) == before
    assert len(fake.calls) == 7


def test_iteration_limit_creates_pending_alert_action(db_session):
    project, task, absence = _fixture(db_session)
    response = {
        "stop_reason": "tool_use",
        "content": [_block("detectConflicts", 1, resource_id=str(uuid4()), start="2026-01-06", end="2026-01-06")],
    }
    fake = FakeLLMClient([response] * 8)

    result = AgentOrchestrator(fake).run(db_session, absence.id)

    assert len(fake.calls) == 8
    assert len(result.actions_created) == 1
    assert result.actions_created[0].statut == AgentActionStatus.EN_ATTENTE


def test_trigger_does_not_call_llm_without_conflict(db_session, monkeypatch):
    _, _, absence = _fixture(db_session)
    monkeypatch.setattr(trigger, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(
        trigger.ResourceAllocationService,
        "detect_conflicts",
        lambda self, resource_id, start, end: [],
    )

    class UnexpectedOrchestrator:
        def run(self, db, unavailability_id):
            raise AssertionError("Le LLM ne doit pas être appelé sans conflit")

    monkeypatch.setattr(trigger, "AgentOrchestrator", UnexpectedOrchestrator)
    trigger.handle_unavailability_created(absence.id)
