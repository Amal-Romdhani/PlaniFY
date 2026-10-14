from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Boolean, CheckConstraint, Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TaskStatus


class Tache(Base):
    __tablename__ = "taches"
    __table_args__ = (
        CheckConstraint("duree >= 0", name="ck_taches_duree_positive"),
        CheckConstraint("avancement BETWEEN 0 AND 100", name="ck_taches_avancement"),
        CheckConstraint("marge >= 0", name="ck_taches_marge_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(
        ForeignKey("projets.id", ondelete="CASCADE")
    )
    jalon_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jalons.id", ondelete="SET NULL")
    )
    nom: Mapped[str] = mapped_column(String(255))
    competences_requises: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    duree: Mapped[int] = mapped_column(Integer)
    date_debut_prevue: Mapped[date] = mapped_column(Date)
    date_fin_prevue: Mapped[date] = mapped_column(Date)
    avancement: Mapped[int] = mapped_column(Integer, default=0)
    est_critique: Mapped[bool] = mapped_column(Boolean, default=False)
    marge: Mapped[int] = mapped_column(Integer, default=0)
    statut: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"))

    projet: Mapped[Projet] = relationship(back_populates="taches")
    jalon: Mapped[Jalon | None] = relationship(back_populates="taches")
    affectations: Mapped[list[Affectation]] = relationship(
        back_populates="tache", cascade="all, delete-orphan"
    )
    dependances_amont: Mapped[list[Dependance]] = relationship(
        back_populates="tache_amont",
        foreign_keys="Dependance.tache_amont_id",
        cascade="all, delete-orphan",
    )
    dependances_aval: Mapped[list[Dependance]] = relationship(
        back_populates="tache_aval",
        foreign_keys="Dependance.tache_aval_id",
        cascade="all, delete-orphan",
    )
    actions_agent: Mapped[list[ActionAgent]] = relationship(back_populates="tache")
