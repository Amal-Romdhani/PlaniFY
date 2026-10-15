from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.enums import ResourceType, UserRole
from app.models.ressource import Ressource
from app.models.utilisateur import Utilisateur


DEMO_USERS: tuple[tuple[str, str, str, UserRole], ...] = (
    ("Administrateur", "admin@planify.local", "Admin123!", UserRole.ADMIN),
    (
        "Chef de projet",
        "chef@planify.local",
        "Chef123!",
        UserRole.CHEF_PROJET,
    ),
    ("Membre", "membre@planify.local", "Membre123!", UserRole.MEMBRE),
)


def create_or_update_demo_users(
    db: Session,
    users: Iterable[tuple[str, str, str, UserRole]] = DEMO_USERS,
) -> int:
    """Crée ou réinitialise les comptes de démonstration."""

    updated_count = 0
    member: Utilisateur | None = None

    for nom, email, password, role in users:
        user = db.scalar(select(Utilisateur).where(Utilisateur.email == email))
        if user is None:
            user = Utilisateur(
                nom=nom,
                email=email,
                mot_de_passe_hash=hash_password(password),
                role=role,
            )
            db.add(user)
        else:
            user.nom = nom
            user.mot_de_passe_hash = hash_password(password)
            user.role = role

        if email == "membre@planify.local":
            member = user
        updated_count += 1

    db.flush()
    if member is None:
        raise ValueError("Le compte membre de démonstration est introuvable.")

    resource = db.scalar(
        select(Ressource).where(Ressource.utilisateur_id == member.id)
    )
    if resource is None:
        db.add(
            Ressource(
                nom=member.nom,
                type=ResourceType.HUMAINE,
                competences=[],
                charge_max=8,
                utilisateur_id=member.id,
            )
        )
    else:
        resource.nom = member.nom
        resource.type = ResourceType.HUMAINE
        resource.charge_max = 8

    return updated_count


def main() -> None:
    """Initialise les comptes de démonstration dans la base configurée."""

    with SessionLocal() as db:
        updated_count = create_or_update_demo_users(db)
        db.commit()

    print(f"{updated_count} comptes créés/mis à jour")


if __name__ == "__main__":
    main()
