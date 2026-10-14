from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    nom: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))

    projets_diriges: Mapped[list["Projet"]] = relationship(
        back_populates="chef", foreign_keys="Projet.chef_id"
    )
    ressource: Mapped["Ressource | None"] = relationship(
        back_populates="utilisateur", uselist=False
    )
    actions_decidees: Mapped[list["ActionAgent"]] = relationship(
        back_populates="decideur", foreign_keys="ActionAgent.decideur_id"
    )
