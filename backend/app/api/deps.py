from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.enums import UserRole
from app.models.utilisateur import Utilisateur
from app.repositories.user_repository import UserRepository


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Utilisateur:
    """Retourne l'utilisateur authentifié."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        subject = payload.get("sub")
        if not subject:
            raise credentials_exception
        user_id = UUID(str(subject))
    except (ValueError, TypeError):
        raise credentials_exception

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user


def require_roles(*roles: UserRole) -> Callable[..., Any]:
    """Construit une dépendance de contrôle des rôles."""

    def role_dependency(
        current_user: Utilisateur = Depends(get_current_user),
    ) -> Utilisateur:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes",
            )
        return current_user

    return role_dependency
