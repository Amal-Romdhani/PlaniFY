from datetime import date
from uuid import uuid4

from app.agent.tools import TOOLS, execute_tool
from app.models.projet import Projet
from app.models.tache import Tache
from app.models.enums import ProjectStatus, TaskStatus
from app.models.utilisateur import Utilisateur


def _assert_no_sensitive_terms(value: object) -> None:
    forbidden = ("motif", "maladie", "conge")
    if isinstance(value, dict):
        for key, item in value.items():
            assert not any(term in str(key).lower() for term in forbidden)
            _assert_no_sensitive_terms(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_sensitive_terms(item)
    elif isinstance(value, str):
        assert not any(term in value.lower() for term in forbidden)


def _project(db_session):
    chef = Utilisateur(
        nom="Chef outil",
        email=f"{uuid4()}@example.com",
        mot_de_passe_hash="hash",
        role="CHEF_PROJET",
    )
    project = Projet(
        nom="Projet outil",
        date_debut=date(2026, 1, 5),
        date_fin=date(2026, 1, 30),
        statut=ProjectStatus.PLANIFIE,
        chef=chef,
    )
    task = Tache(
        projet=project,
        nom="Tâche outil",
        duree=3,
        date_debut_prevue=date(2026, 1, 5),
        date_fin_prevue=date(2026, 1, 7),
        statut=TaskStatus.A_FAIRE,
    )
    db_session.add_all([chef, project, task])
    db_session.flush()
    return project, task


def test_all_tool_outputs_are_rgpd_safe(db_session) -> None:
    project, task = _project(db_session)
    db_session.commit = db_session.flush
    args_by_name = {
        "getResourceAvailability": {
            "resource_id": str(uuid4()),
            "start": "2026-01-05",
            "end": "2026-01-09",
        },
        "detectConflicts": {
            "resource_id": str(uuid4()),
            "start": "2026-01-05",
            "end": "2026-01-09",
        },
        "computeCriticalPath": {"project_id": str(project.id)},
        "findReplacementCandidates": {"task_id": str(task.id)},
        "rescheduleTask": {
            "task_id": str(task.id),
            "strategy": "DECALAGE",
            "delay_days": 1,
        },
        "notifyStakeholder": {
            "project_id": str(project.id),
            "task_id": str(task.id),
            "strategy": "DECALAGE",
            "params": {"delay_days": 1},
            "justification": "Tester une proposition",
        },
    }
    outputs = [
        execute_tool(name, args_by_name[name], db_session)
        for name in TOOLS
    ]
    for output in outputs:
        _assert_no_sensitive_terms(output)


def test_simulation_and_notification_do_not_change_task_dates(db_session) -> None:
    project, task = _project(db_session)
    db_session.commit = db_session.flush
    before = (task.date_debut_prevue, task.date_fin_prevue)

    simulation = execute_tool(
        "rescheduleTask",
        {
            "task_id": str(task.id),
            "strategy": "DECALAGE",
            "delay_days": 2,
        },
        db_session,
    )
    assert "error" not in simulation
    db_session.refresh(task)
    assert (task.date_debut_prevue, task.date_fin_prevue) == before

    notification = execute_tool(
        "notifyStakeholder",
        {
            "project_id": str(project.id),
            "task_id": str(task.id),
            "strategy": "DECALAGE",
            "params": {"delay_days": 2},
            "justification": "Décalage proposé après analyse",
        },
        db_session,
    )
    assert "error" not in notification
    assert notification["planning_modified"] is False
    db_session.refresh(task)
    assert (task.date_debut_prevue, task.date_fin_prevue) == before
