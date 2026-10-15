from datetime import date

from fastapi.testclient import TestClient

from app.models.action_agent import ActionAgent
from app.models.enums import AgentActionStatus, AgentActionType, ProjectStatus, TaskStatus, UserRole
from app.models.projet import Projet
from app.models.tache import Tache
from app.models.utilisateur import Utilisateur


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _action(db_session):
    chef = db_session.query(Utilisateur).filter_by(role=UserRole.CHEF_PROJET).first()
    project = Projet(
        nom="Projet actions",
        date_debut=date(2026, 4, 6),
        date_fin=date(2026, 4, 30),
        statut=ProjectStatus.PLANIFIE,
        chef_id=chef.id,
    )
    task = Tache(
        projet=project,
        nom="Tâche action",
        duree=2,
        date_debut_prevue=date(2026, 4, 6),
        date_fin_prevue=date(2026, 4, 7),
        statut=TaskStatus.A_FAIRE,
    )
    action = ActionAgent(
        projet=project,
        tache=task,
        type=AgentActionType.DECALAGE,
        justification="Décalage simulé",
        payload={
            "params": {"delay_days": 1},
            "simulation_result": {
                "ancienne_date_fin_tache": "2026-04-07",
                "ancienne_date_fin_projet": "2026-04-30",
            },
        },
        statut=AgentActionStatus.EN_ATTENTE,
    )
    db_session.add_all([project, task, action])
    db_session.flush()
    return chef, project, task, action


def test_accept_uses_stored_payload_and_double_decision_is_rejected(client, db_session):
    chef, _, task, action = _action(db_session)
    headers = _login(client, chef.email, "chef-password")

    accepted = client.post(
        f"/agent/actions/{action.id}/accept",
        headers=headers,
    )
    assert accepted.status_code == 200, accepted.text
    db_session.refresh(task)
    assert task.date_debut_prevue == date(2026, 4, 7)
    assert client.post(f"/agent/actions/{action.id}/accept", headers=headers).status_code == 409


def test_reject_does_not_change_planning_and_member_is_forbidden(client, db_session):
    chef, _, task, action = _action(db_session)
    before = (task.date_debut_prevue, task.date_fin_prevue)
    member_headers = _login(client, "member@test.local", "member-password")

    assert client.post(f"/agent/actions/{action.id}/reject", headers=member_headers).status_code == 403
    rejected = client.post(f"/agent/actions/{action.id}/reject", headers=_login(client, chef.email, "chef-password"))
    assert rejected.status_code == 200
    db_session.refresh(task)
    assert (task.date_debut_prevue, task.date_fin_prevue) == before


def test_modified_planning_is_rejected(client, db_session):
    chef, _, task, action = _action(db_session)
    task.date_fin_prevue = date(2026, 4, 8)
    db_session.flush()

    response = client.post(
        f"/agent/actions/{action.id}/accept",
        headers=_login(client, chef.email, "chef-password"),
    )
    assert response.status_code == 409
    assert "planning modifié, relancer la simulation" in response.json()["detail"]


def test_modify_resimulates_without_changing_dates(client, db_session, monkeypatch):
    chef, _, task, action = _action(db_session)
    before = (task.date_debut_prevue, task.date_fin_prevue)
    monkeypatch.setattr(
        "app.routers.agent_router.simulate_delay",
        lambda db, task_id, delay: __import__(
            "app.services.reschedule_service", fromlist=["simulate_delay"]
        ).simulate_delay(db, task_id, delay),
    )

    response = client.post(
        f"/agent/actions/{action.id}/modify",
        json={"strategy": "DECALAGE", "delay_days": 2},
        headers=_login(client, chef.email, "chef-password"),
    )
    assert response.status_code == 200, response.text
    db_session.refresh(task)
    assert (task.date_debut_prevue, task.date_fin_prevue) == before
    assert response.json()["payload"]["params"]["delay_days"] == 2
