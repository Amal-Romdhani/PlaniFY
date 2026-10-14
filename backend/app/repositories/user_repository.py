from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.utilisateur import Utilisateur


class UserRepository:
    """Accès aux utilisateurs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> Utilisateur | None:
        """Retourne un utilisateur par identifiant."""

        return self.db.get(Utilisateur, user_id)

    def get_by_email(self, email: str) -> Utilisateur | None:
        """Retourne un utilisateur par adresse email."""

        return self.db.scalar(select(Utilisateur).where(Utilisateur.email == email))

    def create(
        self,
        *,
        nom: str,
        email: str,
        mot_de_passe_hash: str,
        role: UserRole,
    ) -> Utilisateur:
        """Crée un utilisateur."""

        user = Utilisateur(
            nom=nom,
            email=email,
            mot_de_passe_hash=mot_de_passe_hash,
            role=role,
        )
        self.db.add(user)
        self.db.flush()
        return user
