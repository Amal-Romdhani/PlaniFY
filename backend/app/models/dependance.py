from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DependencyType


class Dependance(Base):
    __tablename__ = "dependances"
    __table_args__ = (
        UniqueConstraint(
            "tache_amont_id", "tache_aval_id", name="uq_dependances_taches"
        ),
        CheckConstraint(
            "tache_amont_id <> tache_aval_id", name="ck_dependances_taches_distinctes"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tache_amont_id: Mapped[UUID] = mapped_column(
        ForeignKey("taches.id", ondelete="CASCADE")
    )
    tache_aval_id: Mapped[UUID] = mapped_column(
        ForeignKey("taches.id", ondelete="CASCADE")
    )
    type: Mapped[DependencyType] = mapped_column(
        Enum(DependencyType, name="dependency_type"), default=DependencyType.FIN_DEBUT
    )

    tache_amont: Mapped[Tache] = relationship(
        back_populates="dependances_amont", foreign_keys=[tache_amont_id]
    )
    tache_aval: Mapped[Tache] = relationship(
        back_populates="dependances_aval", foreign_keys=[tache_aval_id]
    )
