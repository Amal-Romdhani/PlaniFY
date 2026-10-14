from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import hash_password
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
from app.repositories.user_repository import UserRepository
from app.schemas.entities import (
    AssignmentCreate, AssignmentRead, AssignmentUpdate, DependencyCreate,
    DependencyRead, DependencyUpdate, MilestoneCreate, MilestoneRead,
    MilestoneUpdate, ProjectCreate, ProjectRead, ProjectUpdate, ResourceCreate,
    ResourceRead, ResourceUpdate, TaskCreate, TaskRead, TaskUpdate,
    UnavailabilityCreate, UnavailabilityRead, UnavailabilityUpdate,
)
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import crud_service as service


router = APIRouter()


def save(db: Session) -> None:
    db.commit()


def remove(db: Session, entity: object) -> Response:
    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> list[Projet]:
    query = select(Projet) if user.role == UserRole.ADMIN else select(Projet).where(Projet.chef_id == user.id)
    return list(db.scalars(query).all())


@router.post("/projects", response_model=ProjectRead, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Projet:
    result = service.create_project(db, user, data.model_dump())
    save(db)
    return result


@router.get("/projects/{project_id}", response_model=ProjectRead)
def read_project(project_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> Projet:
    return service.get_project(db, project_id, user)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: UUID, data: ProjectUpdate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Projet:
    project = service.get_project(db, project_id, user)
    result = service.update_project(db, project, data.model_dump(exclude_unset=True))
    save(db)
    return result


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Response:
    return remove(db, service.get_project(db, project_id, user))


@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead])
def list_tasks(project_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> list[Tache]:
    project = service.get_project(db, project_id, user) if user.role != UserRole.MEMBRE else db.get(Projet, project_id)
    if project is None:
        raise service.not_found("Projet")
    if user.role == UserRole.MEMBRE:
        return list(db.scalars(select(Tache).join(Affectation).join(Ressource).where(
            Tache.projet_id == project_id, Ressource.utilisateur_id == user.id
        )).all())
    return list(db.scalars(select(Tache).where(Tache.projet_id == project_id)).all())


@router.post("/projects/{project_id}/tasks", response_model=TaskRead, status_code=201)
def create_task(project_id: UUID, data: TaskCreate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Tache:
    service.get_project(db, project_id, user)
    result = service.create_task(db, project_id, data.model_dump())
    save(db)
    return result


@router.get("/tasks/{task_id}", response_model=TaskRead)
def read_task(task_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> Tache:
    task = service.get_task(db, task_id)
    service.ensure_task_access(db, task, user)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: UUID, data: TaskUpdate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Tache:
    task = service.get_task(db, task_id)
    service.ensure_task_access(db, task, user, write=True)
    result = service.update_task(db, task, data.model_dump(exclude_unset=True))
    save(db)
    return result


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Response:
    task = service.get_task(db, task_id)
    service.ensure_task_access(db, task, user, write=True)
    return remove(db, task)


@router.get("/tasks/{task_id}/dependencies", response_model=list[DependencyRead])
def list_dependencies(task_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> list[Dependance]:
    task = service.get_task(db, task_id)
    service.ensure_task_access(db, task, user)
    return list(db.scalars(select(Dependance).where((Dependance.tache_amont_id == task_id) | (Dependance.tache_aval_id == task_id))).all())


@router.post("/tasks/{task_id}/dependencies", response_model=DependencyRead, status_code=201)
def create_dependency(task_id: UUID, data: DependencyCreate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Dependance:
    task = service.get_task(db, task_id)
    service.ensure_task_access(db, task, user, write=True)
    values = data.model_dump()
    if values["tache_amont_id"] != task_id:
        raise HTTPException(status_code=422, detail="La tâche amont doit correspondre à l'URL")
    result = service.create_dependency(db, task.projet_id, values)
    save(db)
    return result


@router.patch("/dependencies/{dependency_id}", response_model=DependencyRead)
def update_dependency(dependency_id: UUID, data: DependencyUpdate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Dependance:
    dependency = CrudRepository(db, Dependance).get(dependency_id)
    if dependency is None:
        raise service.not_found("Dépendance")
    task = service.get_task(db, dependency.tache_amont_id)
    service.ensure_task_access(db, task, user, write=True)
    result = service.update_dependency(db, dependency, task.projet_id, data.model_dump(exclude_unset=True))
    save(db)
    return result


@router.delete("/dependencies/{dependency_id}", status_code=204)
def delete_dependency(dependency_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Response:
    dependency = CrudRepository(db, Dependance).get(dependency_id)
    if dependency is None:
        raise service.not_found("Dépendance")
    service.ensure_task_access(db, service.get_task(db, dependency.tache_amont_id), user, write=True)
    return remove(db, dependency)


@router.get("/projects/{project_id}/milestones", response_model=list[MilestoneRead])
def list_milestones(project_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> list[Jalon]:
    service.get_project(db, project_id, user)
    return list(db.scalars(select(Jalon).where(Jalon.projet_id == project_id)).all())


@router.post("/projects/{project_id}/milestones", response_model=MilestoneRead, status_code=201)
def create_milestone(project_id: UUID, data: MilestoneCreate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Jalon:
    service.get_project(db, project_id, user)
    result = CrudRepository(db, Jalon).create(projet_id=project_id, **data.model_dump())
    save(db)
    return result


@router.patch("/milestones/{milestone_id}", response_model=MilestoneRead)
def update_milestone(milestone_id: UUID, data: MilestoneUpdate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Jalon:
    milestone = CrudRepository(db, Jalon).get(milestone_id)
    if milestone is None:
        raise service.not_found("Jalon")
    service.get_project(db, milestone.projet_id, user)
    result = CrudRepository(db, Jalon).update(milestone, **data.model_dump(exclude_unset=True))
    save(db)
    return result


@router.delete("/milestones/{milestone_id}", status_code=204)
def delete_milestone(milestone_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Response:
    milestone = CrudRepository(db, Jalon).get(milestone_id)
    if milestone is None:
        raise service.not_found("Jalon")
    service.get_project(db, milestone.projet_id, user)
    return remove(db, milestone)


@router.get("/resources", response_model=list[ResourceRead])
def list_resources(db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> list[Ressource]:
    if user.role == UserRole.ADMIN:
        return list(db.scalars(select(Ressource)).all())
    if user.ressource is None:
        return []
    return [user.ressource]


@router.post("/resources", response_model=ResourceRead, status_code=201)
def create_resource(data: ResourceCreate, db: Session = Depends(get_db), _: Utilisateur = Depends(require_roles(UserRole.ADMIN))) -> Ressource:
    result = CrudRepository(db, Ressource).create(**data.model_dump())
    save(db)
    return result


@router.patch("/resources/{resource_id}", response_model=ResourceRead)
def update_resource(resource_id: UUID, data: ResourceUpdate, db: Session = Depends(get_db), _: Utilisateur = Depends(require_roles(UserRole.ADMIN))) -> Ressource:
    resource = CrudRepository(db, Ressource).get(resource_id)
    if resource is None:
        raise service.not_found("Ressource")
    result = CrudRepository(db, Ressource).update(resource, **data.model_dump(exclude_unset=True))
    save(db)
    return result


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: UUID, db: Session = Depends(get_db), _: Utilisateur = Depends(require_roles(UserRole.ADMIN))) -> Response:
    resource = CrudRepository(db, Ressource).get(resource_id)
    if resource is None:
        raise service.not_found("Ressource")
    return remove(db, resource)


@router.get("/tasks/{task_id}/assignments", response_model=list[AssignmentRead])
def list_assignments(task_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> list[Affectation]:
    task = service.get_task(db, task_id)
    service.ensure_task_access(db, task, user)
    return list(db.scalars(select(Affectation).where(Affectation.tache_id == task_id)).all())


@router.post("/tasks/{task_id}/assignments", response_model=AssignmentRead, status_code=201)
def create_assignment(task_id: UUID, data: AssignmentCreate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Affectation:
    task = service.get_task(db, task_id)
    service.ensure_task_access(db, task, user, write=True)
    result = service.create_assignment(db, task, data.model_dump())
    save(db)
    return result


@router.patch("/assignments/{assignment_id}", response_model=AssignmentRead)
def update_assignment(assignment_id: UUID, data: AssignmentUpdate, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Affectation:
    assignment = CrudRepository(db, Affectation).get(assignment_id)
    if assignment is None:
        raise service.not_found("Affectation")
    service.ensure_task_access(db, service.get_task(db, assignment.tache_id), user, write=True)
    result = service.update_assignment(db, assignment, data.model_dump(exclude_unset=True))
    save(db)
    return result


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(require_roles(UserRole.CHEF_PROJET))) -> Response:
    assignment = CrudRepository(db, Affectation).get(assignment_id)
    if assignment is None:
        raise service.not_found("Affectation")
    service.ensure_task_access(db, service.get_task(db, assignment.tache_id), user, write=True)
    return remove(db, assignment)


@router.get("/unavailabilities", response_model=list[UnavailabilityRead])
def list_unavailabilities(db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> list[Indisponibilite]:
    if user.role == UserRole.ADMIN:
        return list(db.scalars(select(Indisponibilite)).all())
    if user.role == UserRole.MEMBRE and user.ressource is not None:
        return list(db.scalars(select(Indisponibilite).where(Indisponibilite.ressource_id == user.ressource.id)).all())
    return [item for item in db.scalars(select(Indisponibilite)).all() if service.visible_unavailability(db, item, user)]


@router.post("/unavailabilities", response_model=UnavailabilityRead, status_code=201)
def create_unavailability(data: UnavailabilityCreate, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> Indisponibilite:
    resource = service.resource_for_user(db, user, data.ressource_id)
    if user.role not in (UserRole.ADMIN, UserRole.MEMBRE):
        raise HTTPException(status_code=403, detail="Permissions insuffisantes")
    result = CrudRepository(db, Indisponibilite).create(**data.model_dump())
    save(db)
    return result


@router.patch("/unavailabilities/{item_id}", response_model=UnavailabilityRead)
def update_unavailability(item_id: UUID, data: UnavailabilityUpdate, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> Indisponibilite:
    item = CrudRepository(db, Indisponibilite).get(item_id)
    if item is None:
        raise service.not_found("Indisponibilité")
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permissions insuffisantes")
    values = data.model_dump(exclude_unset=True)
    start = values.get("date_debut", item.date_debut)
    end = values.get("date_fin", item.date_fin)
    if end < start:
        raise HTTPException(status_code=422, detail="Dates d'indisponibilité invalides")
    result = CrudRepository(db, Indisponibilite).update(item, **values)
    save(db)
    return result


@router.delete("/unavailabilities/{item_id}", status_code=204)
def delete_unavailability(item_id: UUID, db: Session = Depends(get_db), user: Utilisateur = Depends(get_current_user)) -> Response:
    item = CrudRepository(db, Indisponibilite).get(item_id)
    if item is None:
        raise service.not_found("Indisponibilité")
    if user.role == UserRole.MEMBRE:
        service.resource_for_user(db, user, item.ressource_id)
    elif user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permissions insuffisantes")
    return remove(db, item)


@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), _: Utilisateur = Depends(require_roles(UserRole.ADMIN))) -> list[Utilisateur]:
    return list(db.scalars(select(Utilisateur)).all())


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: UUID, data: UserUpdate, db: Session = Depends(get_db), _: Utilisateur = Depends(require_roles(UserRole.ADMIN))) -> Utilisateur:
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise service.not_found("Utilisateur")
    values = data.model_dump(exclude_unset=True)
    if "mot_de_passe" in values:
        values["mot_de_passe_hash"] = hash_password(values.pop("mot_de_passe"))
    result = CrudRepository(db, Utilisateur).update(user, **values)
    save(db)
    return result


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: UUID, db: Session = Depends(get_db), _: Utilisateur = Depends(require_roles(UserRole.ADMIN))) -> Response:
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise service.not_found("Utilisateur")
    return remove(db, user)
