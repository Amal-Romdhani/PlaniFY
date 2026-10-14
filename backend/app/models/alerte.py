from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AlertType, RiskLevel


class Alerte(Base):
    __tablename__ = "alertes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projets.id", ondelete="CASCADE")
    )
    type: Mapped[AlertType] = mapped_column(Enum(AlertType, name="alert_type"))
    niveau_risque: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level")
    )
    message: Mapped[str] = mapped_column(Text)
    date_creation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    resolue: Mapped[bool] = mapped_column(Boolean, default=False)

    projet: Mapped[Projet | None] = relationship(back_populates="alertes")
