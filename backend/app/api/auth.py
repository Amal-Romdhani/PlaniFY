from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import UserRole
from app.models.utilisateur import Utilisateur
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead


router = APIRouter()


@router.post("/auth/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Authentifie un utilisateur."""

    user = UserRepository(db).get_by_email(form_data.username)
    if user is None or not verify_password(
        form_data.password, user.mot_de_passe_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/auth/me", response_model=UserRead)
def read_current_user(
    current_user: Utilisateur = Depends(get_current_user),
) -> Utilisateur:
    """Retourne l'utilisateur authentifié."""

    return current_user


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles(UserRole.ADMIN)),
) -> Utilisateur:
    """Crée un compte utilisateur réservé aux administrateurs."""

    repository = UserRepository(db)
    if repository.get_by_email(str(user_data.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email est déjà utilisée",
        )
    try:
        user = repository.create(
            nom=user_data.nom,
            email=str(user_data.email),
            mot_de_passe_hash=hash_password(user_data.mot_de_passe),
            role=user_data.role,
        )
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de créer cet utilisateur",
        ) from error
