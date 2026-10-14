from collections.abc import Iterable

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.utilisateur import Utilisateur
from app.repositories.user_repository import UserRepository


DEMO_USERS: tuple[tuple[str, str, str, UserRole], ...] = (
    ("Administrateur", "admin@planify.local", "admin123", UserRole.ADMIN),
    ("Chef de projet", "chef@planify.local", "chef12345", UserRole.CHEF_PROJET),
    ("Membre 1", "membre1@planify.local", "membre123", UserRole.MEMBRE),
    ("Membre 2", "membre2@planify.local", "membre123", UserRole.MEMBRE),
    ("Membre 3", "membre3@planify.local", "membre123", UserRole.MEMBRE),
)


def seed_users(users: Iterable[tuple[str, str, str, UserRole]] = DEMO_USERS) -> None:
    """Crée les comptes de démonstration manquants."""

    with SessionLocal() as db:
        repository = UserRepository(db)
        for nom, email, password, role in users:
            if repository.get_by_email(email) is None:
                repository.create(
                    nom=nom,
                    email=email,
                    mot_de_passe_hash=hash_password(password),
                    role=role,
                )
        db.commit()


if __name__ == "__main__":
    seed_users()
