from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ResourceType


class Ressource(Base):
    __tablename__ = "ressources"
    __table_args__ = (UniqueConstraint("utilisateur_id", name="uq_ressources_utilisateur"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    nom: Mapped[str] = mapped_column(String(255))
    type: Mapped[ResourceType] = mapped_column(
        Enum(ResourceType, name="resource_type")
    )
    competences: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    charge_max: Mapped[int] = mapped_column(Integer, default=8)
    utilisateur_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), unique=True
    )

    utilisateur: Mapped[Utilisateur | None] = relationship(
        back_populates="ressource", uselist=False
    )
    affectations: Mapped[list[Affectation]] = relationship(
        back_populates="ressource", cascade="all, delete-orphan"
    )
    indisponibilites: Mapped[list[Indisponibilite]] = relationship(
        back_populates="ressource", cascade="all, delete-orphan"
    )
