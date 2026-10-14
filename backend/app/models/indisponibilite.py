from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UnavailabilityReason


class Indisponibilite(Base):
    __tablename__ = "indisponibilites"
    __table_args__ = (
        CheckConstraint(
            "date_fin >= date_debut", name="ck_indisponibilites_dates_valides"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ressource_id: Mapped[UUID] = mapped_column(
        ForeignKey("ressources.id", ondelete="CASCADE")
    )
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date] = mapped_column(Date)
    motif: Mapped[UnavailabilityReason] = mapped_column(
        Enum(UnavailabilityReason, name="unavailability_reason")
    )
    source: Mapped[str] = mapped_column(String(50), default="INTERNE")

    ressource: Mapped[Ressource] = relationship(back_populates="indisponibilites")
    actions_agent: Mapped[list[ActionAgent]] = relationship(back_populates="indisponibilite")
