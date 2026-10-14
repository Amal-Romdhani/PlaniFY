from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import MilestoneStatus


class Jalon(Base):
    __tablename__ = "jalons"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(
        ForeignKey("projets.id", ondelete="CASCADE")
    )
    nom: Mapped[str] = mapped_column(String(255))
    date: Mapped[date] = mapped_column(Date)
    statut: Mapped[MilestoneStatus] = mapped_column(
        Enum(MilestoneStatus, name="milestone_status")
    )

    projet: Mapped[Projet] = relationship(back_populates="jalons")
    taches: Mapped[list[Tache]] = relationship(back_populates="jalon")
