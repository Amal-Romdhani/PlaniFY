from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserCreate(BaseModel):
    """Données de création d'un utilisateur."""

    nom: str = Field(min_length=1, max_length=255)
    email: EmailStr
    mot_de_passe: str = Field(min_length=8, max_length=128)
    role: UserRole


class UserRead(BaseModel):
    """Utilisateur exposé par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nom: str
    email: EmailStr
    role: UserRole
