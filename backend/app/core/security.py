from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hache un mot de passe avec bcrypt."""

    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe haché."""

    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: UUID | str) -> str:
    """Crée un jeton JWT d'accès."""

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Décode et valide un jeton JWT."""

    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as error:
        raise ValueError("Jeton invalide") from error
