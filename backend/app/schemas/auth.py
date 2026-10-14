from pydantic import BaseModel

from app.schemas.user import UserRead


class Token(BaseModel):
    """Réponse d'authentification."""

    access_token: str
    token_type: str = "bearer"


class LoginResponse(Token):
    """Réponse de connexion avec l'utilisateur courant."""

    user: UserRead
