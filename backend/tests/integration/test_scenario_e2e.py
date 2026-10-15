from datetime import date

from fastapi.testclient import TestClient

from app.models.action_agent import ActionAgent
from app.models.affectation import Affectation
from app.models.enums import (
    AgentActionStatus,
    AgentActionType,
    ProjectStatus,
    ResourceType,
    TaskStatus,
    UserRole,
)
from app.models.projet import Projet
from app.models.ressource import Ressource
from app.models.tache import Tache
from app.models.utilisateur import Utilisateur


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_unavailability_agent_acceptance_end_to_end(client, db_session, monkeypatch):
    chef = db_session.query(Utilisateur).filter_by(role=UserRole.CHEF_PROJET).first()
    project = Projet(
        nom="Scénario E2E",
        date_debut=date(2026, 4, 6),
        date_fin=date(2026, 4, 30),
        statut=ProjectStatus.PLANIFIE,
        chef_id=chef.id,
    )
    resource = Ressource(
        nom="Ressource E2E",
        type=ResourceType.HUMAINE,
        charge_max=8,
    )
    task = Tache(
        projet=project,
        nom="Tâche E2E",
        duree=2,
        date_debut_prevue=date(2026, 4, 6),
        date_fin_prevue=date(2026, 4, 7),
        statut=TaskStatus.A_FAIRE,
    )
    assignment = Affectation(ressource=resource, tache=task, charge_allouee=2)
    db_session.add_all([project, resource, task, assignment])
    db_session.flush()
    initial_start = task.date_debut_prevue.isoformat()
    initial_end = task.date_fin_prevue.isoformat()

    def fake_agent(unavailability_id):
        action = ActionAgent(
            projet_id=project.id,
            tache_id=task.id,
            indisponibilite_id=unavailability_id,
            type=AgentActionType.DECALAGE,
            justification="Décalage simulé par le scénario.",
            payload={
                "params": {"delay_days": 1},
                "simulation_result": {
                    "ancienne_date_fin_tache": initial_end,
                    "ancienne_date_fin_projet": project.date_fin.isoformat(),
                },
                "planning_snapshot": {
                    "task_start": initial_start,
                    "task_end": initial_end,
                    "project_end": project.date_fin.isoformat(),
                },
            },
            statut=AgentActionStatus.EN_ATTENTE,
        )
        db_session.add(action)
        db_session.flush()

    monkeypatch.setattr("app.api.crud.handle_unavailability_created", fake_agent)
    headers = _login(client, chef.email, "chef-password")
    created = client.post(
        "/unavailabilities",
        json={
            "ressource_id": str(resource.id),
            "date_debut": "2026-04-07",
            "date_fin": "2026-04-07",
            "motif": "AUTRE",
        },
        headers=headers,
    )
    assert created.status_code == 201

    pending = client.get("/agent/actions", headers=headers)
    assert pending.status_code == 200
    action_id = pending.json()[0]["id"]
    accepted = client.post(f"/agent/actions/{action_id}/accept", headers=headers)
    assert accepted.status_code == 200, accepted.text
    db_session.refresh(task)
    assert task.date_debut_prevue == date(2026, 4, 7)
    assert db_session.get(ActionAgent, action_id).statut == AgentActionStatus.ACCEPTEE

    history = client.get(
        "/agent/actions",
        params={"statut": "ACCEPTEE"},
        headers=headers,
    )
    assert history.status_code == 200
    assert history.json()[0]["id"] == action_id
