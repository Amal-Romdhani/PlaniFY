from fastapi.testclient import TestClient


def token(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_project_task_dependency_crud_and_permissions(client: TestClient) -> None:
    admin_headers = token(client, "admin@test.local", "admin-password")
    chef = client.post(
        "/users",
        json={
            "nom": "Chef",
            "email": "chef@example.com",
            "mot_de_passe": "chef-password",
            "role": "CHEF_PROJET",
        },
        headers=admin_headers,
    )
    assert chef.status_code == 201, chef.text
    chef_headers = token(client, "chef@example.com", "chef-password")

    project = client.post(
        "/projects",
        json={
            "nom": "Projet test",
            "date_debut": "2026-01-01",
            "date_fin": "2026-01-31",
            "statut": "PLANIFIE",
        },
        headers=chef_headers,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    task_payload = {
        "nom": "Tâche",
        "duree": 2,
        "date_debut_prevue": "2026-01-02",
        "date_fin_prevue": "2026-01-03",
        "statut": "A_FAIRE",
    }
    first = client.post(f"/projects/{project_id}/tasks", json=task_payload, headers=chef_headers)
    assert first.status_code == 201
    second_payload = {**task_payload, "nom": "Tâche 2", "date_debut_prevue": "2026-01-04", "date_fin_prevue": "2026-01-05"}
    second = client.post(f"/projects/{project_id}/tasks", json=second_payload, headers=chef_headers)
    assert second.status_code == 201

    first_id = first.json()["id"]
    second_id = second.json()["id"]
    dependency = client.post(
        f"/tasks/{first_id}/dependencies",
        json={"tache_amont_id": first_id, "tache_aval_id": second_id, "type": "FIN_DEBUT"},
        headers=chef_headers,
    )
    assert dependency.status_code == 201
    cycle = client.post(
        f"/tasks/{second_id}/dependencies",
        json={"tache_amont_id": second_id, "tache_aval_id": first_id, "type": "FIN_DEBUT"},
        headers=chef_headers,
    )
    assert cycle.status_code == 422

    member_headers = token(client, "member@test.local", "member-password")
    assert client.patch(f"/tasks/{first_id}", json={"nom": "Interdit"}, headers=member_headers).status_code == 403
    assert client.get(f"/projects/{project_id}", headers=member_headers).status_code == 403


def test_validation_and_missing_entities(client: TestClient) -> None:
    admin_headers = token(client, "admin@test.local", "admin-password")
    chef = client.post(
        "/users",
        json={
            "nom": "Chef",
            "email": "chef@example.com",
            "mot_de_passe": "chef-password",
            "role": "CHEF_PROJET",
        },
        headers=admin_headers,
    )
    assert chef.status_code == 201, chef.text
    chef_headers = token(client, "chef@example.com", "chef-password")
    invalid = client.post(
        "/projects",
        json={"nom": "Invalide", "date_debut": "2026-02-01", "date_fin": "2026-01-01", "statut": "PLANIFIE"},
        headers=chef_headers,
    )
    assert invalid.status_code == 422
    missing = client.get("/projects/00000000-0000-0000-0000-000000000000", headers=admin_headers)
    assert missing.status_code == 404


def test_unavailability_permissions_and_overlap(client: TestClient, monkeypatch) -> None:
    admin_headers = token(client, "admin@test.local", "admin-password")
    users = client.get("/users", headers=admin_headers).json()
    member_id = next(user["id"] for user in users if user["email"] == "member@test.local")
    first_resource = client.post(
        "/resources",
        json={"nom": "Membre ressource", "type": "HUMAINE", "charge_max": 8, "utilisateur_id": member_id},
        headers=admin_headers,
    )
    assert first_resource.status_code == 201
    second_resource = client.post(
        "/resources",
        json={"nom": "Autre ressource", "type": "HUMAINE", "charge_max": 8},
        headers=admin_headers,
    )
    assert second_resource.status_code == 201
    member_headers = token(client, "member@test.local", "member-password")
    monkeypatch.setattr("app.api.crud.handle_unavailability_created", lambda _: None)

    own = client.post(
        "/unavailabilities",
        json={
            "ressource_id": first_resource.json()["id"],
            "date_debut": "2026-03-02",
            "date_fin": "2026-03-04",
            "motif": "CONGE",
        },
        headers=member_headers,
    )
    assert own.status_code == 201
    overlap = client.post(
        "/unavailabilities",
        json={
            "ressource_id": first_resource.json()["id"],
            "date_debut": "2026-03-04",
            "date_fin": "2026-03-05",
            "motif": "AUTRE",
        },
        headers=member_headers,
    )
    assert overlap.status_code == 409
    forbidden = client.post(
        "/unavailabilities",
        json={
            "ressource_id": second_resource.json()["id"],
            "date_debut": "2026-03-10",
            "date_fin": "2026-03-11",
            "motif": "CONGE",
        },
        headers=member_headers,
    )
    assert forbidden.status_code == 403
    listed = client.get("/unavailabilities", headers=member_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.delete(f"/unavailabilities/{own.json()['id']}", headers=member_headers).status_code == 204
