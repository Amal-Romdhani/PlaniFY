from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Affectation(Base):
    __tablename__ = "affectations"
    __table_args__ = (
        UniqueConstraint("ressource_id", "tache_id", name="uq_affectations_ressource_tache"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ressource_id: Mapped[UUID] = mapped_column(
        ForeignKey("ressources.id", ondelete="CASCADE")
    )
    tache_id: Mapped[UUID] = mapped_column(
        ForeignKey("taches.id", ondelete="CASCADE")
    )
    charge_allouee: Mapped[int] = mapped_column(Integer)

    ressource: Mapped[Ressource] = relationship(back_populates="affectations")
    tache: Mapped[Tache] = relationship(back_populates="affectations")
