from datetime import date as date_type
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    DependencyType,
    MilestoneStatus,
    ProjectStatus,
    ResourceType,
    TaskStatus,
    UnavailabilityReason,
)


class ReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    description: str | None = None
    date_debut: date_type
    date_fin: date_type
    statut: ProjectStatus = ProjectStatus.PLANIFIE

    @model_validator(mode="after")
    def valid_dates(self) -> "ProjectCreate":
        if self.date_fin < self.date_debut:
            raise ValueError("date_fin doit être postérieure ou égale à date_debut")
        return self


class ProjectUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    date_debut: date_type | None = None
    date_fin: date_type | None = None
    statut: ProjectStatus | None = None


class ProjectRead(ProjectCreate, ReadSchema):
    id: UUID
    chef_id: UUID


class TaskCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    duree: int = Field(ge=0)
    date_debut_prevue: date_type
    date_fin_prevue: date_type
    jalon_id: UUID | None = None
    avancement: int = Field(default=0, ge=0, le=100)
    est_critique: bool = False
    marge: int = Field(default=0, ge=0)
    statut: TaskStatus = TaskStatus.A_FAIRE

    @model_validator(mode="after")
    def valid_dates(self) -> "TaskCreate":
        if self.date_fin_prevue < self.date_debut_prevue:
            raise ValueError("date_fin_prevue doit être postérieure ou égale à date_debut_prevue")
        return self


class TaskUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=255)
    duree: int | None = Field(default=None, ge=0)
    date_debut_prevue: date_type | None = None
    date_fin_prevue: date_type | None = None
    jalon_id: UUID | None = None
    avancement: int | None = Field(default=None, ge=0, le=100)
    est_critique: bool | None = None
    marge: int | None = Field(default=None, ge=0)
    statut: TaskStatus | None = None


class TaskRead(TaskCreate, ReadSchema):
    id: UUID
    projet_id: UUID


class DependencyCreate(BaseModel):
    tache_amont_id: UUID
    tache_aval_id: UUID
    type: DependencyType = DependencyType.FIN_DEBUT


class DependencyUpdate(BaseModel):
    tache_amont_id: UUID | None = None
    tache_aval_id: UUID | None = None
    type: DependencyType | None = None


class DependencyRead(DependencyCreate, ReadSchema):
    id: UUID


class MilestoneCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    date: date_type
    statut: MilestoneStatus = MilestoneStatus.A_VENIR


class MilestoneUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=255)
    date: date_type | None = None
    statut: MilestoneStatus | None = None


class MilestoneRead(MilestoneCreate, ReadSchema):
    id: UUID
    projet_id: UUID


class ResourceCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    type: ResourceType
    competences: list[str] = Field(default_factory=list)
    charge_max: int = Field(default=8, gt=0)
    utilisateur_id: UUID | None = None


class ResourceUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=255)
    type: ResourceType | None = None
    competences: list[str] | None = None
    charge_max: int | None = Field(default=None, gt=0)
    utilisateur_id: UUID | None = None


class ResourceRead(ResourceCreate, ReadSchema):
    id: UUID


class AssignmentCreate(BaseModel):
    ressource_id: UUID
    charge_allouee: int = Field(gt=0)


class AssignmentUpdate(BaseModel):
    ressource_id: UUID | None = None
    charge_allouee: int | None = Field(default=None, gt=0)


class AssignmentRead(AssignmentCreate, ReadSchema):
    id: UUID
    tache_id: UUID


class UnavailabilityCreate(BaseModel):
    ressource_id: UUID
    date_debut: date_type
    date_fin: date_type
    motif: UnavailabilityReason

    @model_validator(mode="after")
    def valid_dates(self) -> "UnavailabilityCreate":
        if self.date_fin < self.date_debut:
            raise ValueError("date_fin doit être postérieure ou égale à date_debut")
        return self


class UnavailabilityUpdate(BaseModel):
    date_debut: date_type | None = None
    date_fin: date_type | None = None
    motif: UnavailabilityReason | None = None


class UnavailabilityRead(UnavailabilityCreate, ReadSchema):
    id: UUID
    source: str
