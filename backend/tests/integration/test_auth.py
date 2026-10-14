from fastapi.testclient import TestClient


def test_login_valide(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        data={"username": "admin@test.local", "password": "admin-password"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_invalide(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        data={"username": "admin@test.local", "password": "mauvais-mot-de-passe"},
    )

    assert response.status_code == 401


def test_acces_sans_jeton(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_auth_me_accepte_un_domaine_local(client: TestClient) -> None:
    login_response = client.post(
        "/auth/login",
        data={"username": "chef@planify.local", "password": "chef-password"},
    )
    assert login_response.status_code == 200

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "chef@planify.local"


def test_acces_avec_mauvais_role(client: TestClient) -> None:
    login_response = client.post(
        "/auth/login",
        data={"username": "member@test.local", "password": "member-password"},
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nom": "Nouveau membre",
            "email": "new@test.local",
            "mot_de_passe": "new-password",
            "role": "MEMBRE",
        },
    )

    assert response.status_code == 403
