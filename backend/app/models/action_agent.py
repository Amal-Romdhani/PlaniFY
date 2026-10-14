from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AgentActionStatus, AgentActionType


class ActionAgent(Base):
    __tablename__ = "agent_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(
        ForeignKey("projets.id", ondelete="CASCADE")
    )
    tache_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("taches.id", ondelete="SET NULL")
    )
    indisponibilite_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("indisponibilites.id", ondelete="SET NULL")
    )
    type: Mapped[AgentActionType] = mapped_column(
        Enum(AgentActionType, name="agent_action_type")
    )
    justification: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    statut: Mapped[AgentActionStatus] = mapped_column(
        Enum(AgentActionStatus, name="agent_action_status"),
        default=AgentActionStatus.EN_ATTENTE,
    )
    date_creation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    date_decision: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decideur_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL")
    )

    projet: Mapped[Projet] = relationship(back_populates="actions_agent")
    tache: Mapped[Tache | None] = relationship(back_populates="actions_agent")
    indisponibilite: Mapped[Indisponibilite | None] = relationship(
        back_populates="actions_agent"
    )
    decideur: Mapped[Utilisateur | None] = relationship(
        back_populates="actions_decidees", foreign_keys=[decideur_id]
    )
