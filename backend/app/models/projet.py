from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ProjectStatus


class Projet(Base):
    __tablename__ = "projets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    nom: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date] = mapped_column(Date)
    statut: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status")
    )
    chef_id: Mapped[UUID] = mapped_column(ForeignKey("utilisateurs.id"))

    chef: Mapped[Utilisateur] = relationship(
        back_populates="projets_diriges", foreign_keys=[chef_id]
    )
    jalons: Mapped[list[Jalon]] = relationship(
        back_populates="projet", cascade="all, delete-orphan"
    )
    taches: Mapped[list[Tache]] = relationship(
        back_populates="projet", cascade="all, delete-orphan"
    )
    actions_agent: Mapped[list[ActionAgent]] = relationship(
        back_populates="projet", cascade="all, delete-orphan"
    )
    alertes: Mapped[list[Alerte]] = relationship(
        back_populates="projet", cascade="all, delete-orphan"
    )
