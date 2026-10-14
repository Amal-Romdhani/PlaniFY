import os
from collections.abc import Generator
import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

import app.models
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.enums import UserRole
from app.models.utilisateur import Utilisateur


def _test_database_url() -> tuple[str, URL, URL]:
    configured_url = make_url(
        os.getenv("DATABASE_URL", settings.database_url)
    )
    database_name = "planify_test"
    admin_url = configured_url.set(database="postgres", drivername="postgresql")
    test_url = configured_url.set(database=database_name)
    return database_name, admin_url, test_url


@pytest.fixture(scope="session")
def test_engine():
    database_name, admin_url, test_url = _test_database_url()
    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
        ).fetchone()
        if exists is None:
            connection.execute(f'CREATE DATABASE "{database_name}"')

    engine = create_engine(test_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    db_session.add_all(
        [
            Utilisateur(
                nom="Admin",
                email="admin@test.local",
                mot_de_passe_hash=hash_password("admin-password"),
                role=UserRole.ADMIN,
            ),
            Utilisateur(
                nom="Membre",
                email="member@test.local",
                mot_de_passe_hash=hash_password("member-password"),
                role=UserRole.MEMBRE,
            ),
        ]
    )
    db_session.flush()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
