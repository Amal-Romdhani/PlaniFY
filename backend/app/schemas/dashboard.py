from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import RiskLevel


class DashboardTaskCounts(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    a_faire: int
    en_cours: int
    terminee: int


class DashboardMilestone(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nom: str
    date: date
    statut: str


class DashboardResourceLoad(BaseModel):
    resource_id: UUID
    nom: str
    pourcentage_utilisation: float
    charge_max: float
    charge_max_journaliere: float
    est_suralouee: bool


class DashboardAlert(BaseModel):
    id: UUID
    type: str
    niveau_risque: str
    message: str
    date_creation: str


class DashboardRiskIndicators(BaseModel):
    taches_critiques_en_retard: int
    conflits_ouverts: int
    ressources_suralouees: int
    niveau_global: RiskLevel


class DashboardResponse(BaseModel):
    avancement_global: float
    date_debut: date
    date_fin_prevue: date
    jours_restants: int
    nb_taches: DashboardTaskCounts
    jalons_a_venir: list[DashboardMilestone]
    jalons_en_retard: list[DashboardMilestone]
    charge_par_ressource: list[DashboardResourceLoad]
    ressources_suralouees: list[UUID]
    risques: DashboardRiskIndicators
    alertes_non_resolues: list[DashboardAlert]
    nb_recommandations_en_attente: int
