from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UnavailablePeriod(BaseModel):
    """Plage d'indisponibilité sans motif RGPD."""

    date_debut: date
    date_fin: date


class ResourceAvailabilityRead(BaseModel):
    """Disponibilité journalière d'une ressource."""

    resource_id: UUID
    days: dict[date, bool]
    unavailable_periods: list[UnavailablePeriod]


class OverallocationPeriodRead(BaseModel):
    """Période de surcharge."""

    date_debut: date
    date_fin: date
    charge: float


class ConflictRead(BaseModel):
    """Conflit entre tâche et indisponibilité."""

    tache_id: UUID
    nom: str
    jours_impactes: int
    est_critique: bool
    marge: int
    plage_indisponible: UnavailablePeriod


class ResourceLoadRead(BaseModel):
    """Charge journalière d'une ressource."""

    resource_id: UUID
    load: dict[date, float]


class CandidateRead(BaseModel):
    """Ressource candidate à un remplacement."""

    resource_id: UUID
    nom: str
    charge_restante: float
    competences: list[str]
