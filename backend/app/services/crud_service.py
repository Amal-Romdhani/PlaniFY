from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.affectation import Affectation
from app.models.dependance import Dependance
from app.models.enums import UserRole
from app.models.indisponibilite import Indisponibilite
from app.models.jalon import Jalon
from app.models.projet import Projet
from app.models.ressource import Ressource
from app.models.tache import Tache
from app.models.utilisateur import Utilisateur
from app.repositories.crud_repository import CrudRepository
from app.services.critical_path_service import recompute_project_schedule
from app.services.graph_utils import has_cycle


def not_found(name: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{name} introuvable")


def ensure_project_chef(project: Projet | None, user: Utilisateur) -> Projet:
    if project is None:
        raise not_found("Projet")
    if user.role != UserRole.ADMIN and project.chef_id != user.id:
        raise HTTPException(status_code=403, detail="Permissions insuffisantes")
    return project


def get_project(db: Session, project_id: UUID, user: Utilisateur) -> Projet:
    return ensure_project_chef(CrudRepository(db, Projet).get(project_id), user)


def create_project(db: Session, user: Utilisateur, values: dict[str, object]) -> Projet:
    values["chef_id"] = user.id
    return CrudRepository(db, Projet).create(**values)


def update_project(db: Session, project: Projet, values: dict[str, object]) -> Projet:
    start = values.get("date_debut", project.date_debut)
    end = values.get("date_fin", project.date_fin)
    if isinstance(start, date) and isinstance(end, date) and end < start:
        raise HTTPException(status_code=422, detail="Dates du projet invalides")
    return CrudRepository(db, Projet).update(project, **values)


def get_task(db: Session, task_id: UUID) -> Tache:
    task = CrudRepository(db, Tache).get(task_id)
    if task is None:
        raise not_found("Tâche")
    return task


def ensure_task_access(db: Session, task: Tache, user: Utilisateur, write: bool = False) -> None:
    project = CrudRepository(db, Projet).get(task.projet_id)
    if project is None:
        raise not_found("Projet")
    if user.role == UserRole.CHEF_PROJET and project.chef_id == user.id:
        return
    if user.role == UserRole.ADMIN and not write:
        return
    if user.role == UserRole.MEMBRE and not write and user.ressource is not None:
        if db.scalar(select(Affectation.id).where(
            Affectation.tache_id == task.id,
            Affectation.ressource_id == user.ressource.id,
        )) is not None:
            return
    raise HTTPException(status_code=403, detail="Permissions insuffisantes")


def create_task(db: Session, project_id: UUID, values: dict[str, object]) -> Tache:
    task = CrudRepository(db, Tache).create(projet_id=project_id, **values)
    recompute_project_schedule(db, project_id)
    return task


def update_task(db: Session, task: Tache, values: dict[str, object]) -> Tache:
    start = values.get("date_debut_prevue", task.date_debut_prevue)
    end = values.get("date_fin_prevue", task.date_fin_prevue)
    if isinstance(start, date) and isinstance(end, date) and end < start:
        raise HTTPException(status_code=422, detail="Dates de la tâche invalides")
    result = CrudRepository(db, Tache).update(task, **values)
    recompute_project_schedule(db, task.projet_id)
    return result


def dependency_edges(db: Session, project_id: UUID, exclude: UUID | None = None) -> list[tuple[UUID, UUID]]:
    query = select(Dependance).join(Tache, Dependance.tache_amont_id == Tache.id).where(
        Tache.projet_id == project_id
    )
    if exclude is not None:
        query = query.where(Dependance.id != exclude)
    return [(item.tache_amont_id, item.tache_aval_id) for item in db.scalars(query).all()]


def validate_dependency(db: Session, source: UUID, target: UUID, project_id: UUID, exclude: UUID | None = None) -> None:
    if source == target:
        raise HTTPException(status_code=422, detail="Une tâche ne peut pas dépendre d'elle-même")
    tasks = db.scalars(select(Tache).where(Tache.id.in_([source, target]), Tache.projet_id == project_id)).all()
    if len(tasks) != 2:
        raise not_found("Tâche")
    if has_cycle(dependency_edges(db, project_id, exclude), (source, target)):
        raise HTTPException(status_code=422, detail="La dépendance crée un cycle")


def create_dependency(db: Session, project_id: UUID, values: dict[str, object]) -> Dependance:
    validate_dependency(db, values["tache_amont_id"], values["tache_aval_id"], project_id)  # type: ignore[arg-type]
    dependency = CrudRepository(db, Dependance).create(**values)
    recompute_project_schedule(db, project_id)
    return dependency


def update_dependency(db: Session, dependency: Dependance, project_id: UUID, values: dict[str, object]) -> Dependance:
    source = values.get("tache_amont_id", dependency.tache_amont_id)
    target = values.get("tache_aval_id", dependency.tache_aval_id)
    validate_dependency(db, source, target, project_id, dependency.id)  # type: ignore[arg-type]
    result = CrudRepository(db, Dependance).update(dependency, **values)
    recompute_project_schedule(db, project_id)
    return result


def create_assignment(db: Session, task: Tache, values: dict[str, object]) -> Affectation:
    resource = CrudRepository(db, Ressource).get(values["ressource_id"])  # type: ignore[arg-type]
    if resource is None:
        raise not_found("Ressource")
    current = db.scalar(select(func.coalesce(func.sum(Affectation.charge_allouee), 0)).where(
        Affectation.ressource_id == resource.id,
        Affectation.id != values.get("id"),
    )) or 0
    if current + values["charge_allouee"] > resource.charge_max:  # type: ignore[operator]
        raise HTTPException(status_code=422, detail="La charge dépasse la charge maximale")
    return CrudRepository(db, Affectation).create(tache_id=task.id, **values)


def update_assignment(db: Session, assignment: Affectation, values: dict[str, object]) -> Affectation:
    resource_id = values.get("ressource_id", assignment.ressource_id)
    resource = CrudRepository(db, Ressource).get(resource_id)  # type: ignore[arg-type]
    if resource is None:
        raise not_found("Ressource")
    current = db.scalar(select(func.coalesce(func.sum(Affectation.charge_allouee), 0)).where(
        Affectation.ressource_id == resource.id,
        Affectation.id != assignment.id,
    )) or 0
    charge = values.get("charge_allouee", assignment.charge_allouee)
    if current + charge > resource.charge_max:  # type: ignore[operator]
        raise HTTPException(status_code=422, detail="La charge dépasse la charge maximale")
    return CrudRepository(db, Affectation).update(assignment, **values)


def resource_for_user(db: Session, user: Utilisateur, resource_id: UUID) -> Ressource:
    resource = CrudRepository(db, Ressource).get(resource_id)
    if resource is None:
        raise not_found("Ressource")
    if user.role == UserRole.MEMBRE and resource.utilisateur_id != user.id:
        raise HTTPException(status_code=403, detail="Permissions insuffisantes")
    return resource


def visible_unavailability(db: Session, item: Indisponibilite, user: Utilisateur) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.MEMBRE:
        return item.ressource.utilisateur_id == user.id
    return db.scalar(select(Projet.id).join(Tache, Tache.projet_id == Projet.id)
                     .join(Affectation, Affectation.tache_id == Tache.id)
                     .where(Projet.chef_id == user.id, Affectation.ressource_id == item.ressource_id)) is not None
