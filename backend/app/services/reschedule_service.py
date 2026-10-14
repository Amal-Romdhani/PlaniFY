from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action_agent import ActionAgent
from app.models.affectation import Affectation
from app.models.enums import AgentActionStatus, AgentActionType, ResourceType, UserRole
from app.models.indisponibilite import Indisponibilite
from app.models.ressource import Ressource
from app.models.tache import Tache
from app.models.utilisateur import Utilisateur
from app.services.critical_path_service import (
    CPMTaskResult,
    Dep,
    TaskNode,
    WorkCalendar,
    compute_cpm,
    recompute_project_schedule,
)
from app.services.resource_allocation_service import (
    AllocationResource,
    AllocationTask,
    Conflict,
    UnavailablePeriod,
    compute_conflicts,
    compute_overallocation,
    compute_replacement_candidates,
)


@dataclass(frozen=True)
class SimulationResult:
    """Résultat chiffré et vérifiable d'une simulation."""

    task_id: UUID
    ancienne_date_fin_tache: date
    nouvelle_date_fin_tache: date
    ancienne_date_fin_projet: date
    nouvelle_date_fin_projet: date
    retard_projet_jours: int
    taches_nouvellement_critiques: list[UUID] = field(default_factory=list)
    nouveaux_conflits: list[Conflict] = field(default_factory=list)
    ressource_actuelle_id: UUID | None = None
    nouvelle_ressource_id: UUID | None = None
    reaffectation_possible: bool | None = None
    problemes: list[str] = field(default_factory=list)


def _project_data(
    db: Session,
    task_id: UUID,
) -> tuple[Tache, date, list[Tache], list[Dep], WorkCalendar]:
    task = db.get(Tache, task_id)
    if task is None:
        raise ValueError("Tâche introuvable")
    tasks = list(db.scalars(select(Tache).where(Tache.projet_id == task.projet_id)).all())
    task_ids = {item.id for item in tasks}
    from app.models.dependance import Dependance

    dependencies = list(
        db.scalars(
            select(Dependance).where(
                Dependance.tache_amont_id.in_(task_ids),
                Dependance.tache_aval_id.in_(task_ids),
            )
        ).all()
    )
    project = task.projet
    return (
        task,
        project.date_debut,
        tasks,
        [Dep(item.tache_amont_id, item.tache_aval_id) for item in dependencies],
        WorkCalendar(),
    )


def _schedule_with_delay(
    tasks: list[Tache],
    dependencies: list[Dep],
    project_start: date,
    calendar: WorkCalendar,
    delayed_task_id: UUID,
    delay_days: int,
) -> tuple[dict[UUID, CPMTaskResult], date]:
    """Construit en mémoire un CPM contraint par un retard de tâche."""

    baseline = compute_cpm(
        [TaskNode(item.id, item.duree) for item in tasks],
        dependencies,
        project_start,
        calendar,
    )
    successors: dict[UUID, list[UUID]] = defaultdict(list)
    predecessors: dict[UUID, list[UUID]] = defaultdict(list)
    for dependency in dependencies:
        successors[dependency.amont_id].append(dependency.aval_id)
        predecessors[dependency.aval_id].append(dependency.amont_id)

    order = baseline.critical_path + [
        item.id for item in tasks if item.id not in baseline.critical_path
    ]
    order = sorted(order, key=lambda item: (baseline.tasks[item].es, str(item)))
    es = {item.id: baseline.tasks[item.id].es for item in tasks}
    ef = {item.id: baseline.tasks[item.id].ef for item in tasks}
    delayed_start = calendar.add_working_days(
        baseline.tasks[delayed_task_id].es,
        delay_days,
    )
    es[delayed_task_id] = max(es[delayed_task_id], delayed_start)
    task_by_id = {item.id: item for item in tasks}
    for task_id in order:
        if task_id == delayed_task_id:
            continue
        if predecessors[task_id]:
            es[task_id] = max(
                es[task_id],
                max(calendar.add_working_days(ef[parent], 1) for parent in predecessors[task_id]),
            )
        ef[task_id] = (
            es[task_id]
            if task_by_id[task_id].duree == 0
            else calendar.add_working_days(es[task_id], task_by_id[task_id].duree - 1)
        )
    ef[delayed_task_id] = (
        es[delayed_task_id]
        if task_by_id[delayed_task_id].duree == 0
        else calendar.add_working_days(es[delayed_task_id], task_by_id[delayed_task_id].duree - 1)
    )
    project_finish = max(ef.values(), default=project_start)
    lf: dict[UUID, date] = {}
    ls: dict[UUID, date] = {}
    for task_id in reversed(order):
        latest_finish = min(
            (calendar.add_working_days(ls[child], -1) for child in successors[task_id]),
            default=project_finish,
        )
        lf[task_id] = latest_finish
        duration = task_by_id[task_id].duree
        ls[task_id] = latest_finish if duration == 0 else calendar.add_working_days(latest_finish, -(duration - 1))
    result = {
        task_id: CPMTaskResult(
            es=es[task_id],
            ef=ef[task_id],
            ls=ls[task_id],
            lf=lf[task_id],
            marge=calendar.working_days_between(es[task_id], ls[task_id]),
            est_critique=es[task_id] == ls[task_id],
        )
        for task_id in task_by_id
    }
    return result, project_finish


def _task_allocations(
    db: Session,
    resource_id: UUID,
) -> list[AllocationTask]:
    rows = db.execute(
        select(Tache, Affectation.charge_allouee)
        .join(Affectation, Affectation.tache_id == Tache.id)
        .where(Affectation.ressource_id == resource_id)
    ).all()
    return [
        AllocationTask(
            task.id,
            task.nom,
            task.date_debut_prevue,
            task.date_fin_prevue,
            float(charge),
            task.est_critique,
            task.marge,
            task.statut,
            task.competences_requises,
        )
        for task, charge in rows
    ]


def simulate_delay(
    db: Session,
    task_id: UUID,
    delay_days: int,
) -> SimulationResult:
    """Simule un retard sans modifier ni valider la session DB."""

    if delay_days < 0:
        raise ValueError("Le retard doit être positif ou nul")
    task, project_start, tasks, dependencies, calendar = _project_data(db, task_id)
    baseline = compute_cpm(
        [TaskNode(item.id, item.duree) for item in tasks],
        dependencies,
        project_start,
        calendar,
    )
    simulated, project_finish = _schedule_with_delay(
        tasks, dependencies, project_start, calendar, task_id, delay_days
    )
    newly_critical = [
        item.id
        for item in tasks
        if not baseline.tasks[item.id].est_critique and simulated[item.id].est_critique
    ]
    conflicts: list[Conflict] = []
    assignment = db.scalar(select(Affectation).where(Affectation.tache_id == task_id))
    if assignment is not None:
        resource = db.get(Ressource, assignment.ressource_id)
        if resource is not None:
            periods = [
                UnavailablePeriod(item.date_debut, item.date_fin)
                for item in db.scalars(
                    select(Indisponibilite).where(
                        Indisponibilite.ressource_id == resource.id
                    )
                ).all()
            ]
            simulated_task = AllocationTask(
                task.id,
                task.nom,
                simulated[task.id].es,
                simulated[task.id].ef,
                float(assignment.charge_allouee),
                simulated[task.id].est_critique,
                simulated[task.id].marge,
                task.statut,
                task.competences_requises,
            )
            conflicts = compute_conflicts(
                simulated[task.id].es,
                simulated[task.id].ef,
                [simulated_task],
                periods,
                calendar,
            )
    return SimulationResult(
        task_id,
        baseline.tasks[task_id].ef,
        simulated[task_id].ef,
        baseline.date_fin_projet,
        project_finish,
        calendar.working_days_between(baseline.date_fin_projet, project_finish),
        newly_critical,
        conflicts,
    )


def simulate_reassignment(
    db: Session,
    task_id: UUID,
    new_resource_id: UUID,
) -> SimulationResult:
    """Simule une réaffectation sans modifier ni valider la session DB."""

    task, project_start, tasks, dependencies, calendar = _project_data(db, task_id)
    baseline = compute_cpm(
        [TaskNode(item.id, item.duree) for item in tasks],
        dependencies,
        project_start,
        calendar,
    )
    assignment = db.scalar(select(Affectation).where(Affectation.tache_id == task_id))
    new_resource = db.get(Ressource, new_resource_id)
    problems: list[str] = []
    if new_resource is None:
        problems.append("Nouvelle ressource introuvable")
    if assignment is not None and assignment.ressource_id == new_resource_id:
        problems.append("La nouvelle ressource est identique à l'actuelle")
    if new_resource is not None:
        periods = [
            UnavailablePeriod(item.date_debut, item.date_fin)
            for item in db.scalars(
                select(Indisponibilite).where(
                    Indisponibilite.ressource_id == new_resource_id
                )
            ).all()
        ]
        if any(
            period.date_debut <= task.date_fin_prevue
            and period.date_fin >= task.date_debut_prevue
            for period in periods
        ):
            problems.append("La nouvelle ressource est indisponible sur la période")
        load = compute_overallocation(
            task.date_debut_prevue,
            task.date_fin_prevue,
            float(new_resource.charge_max),
            _task_allocations(db, new_resource_id),
            calendar,
        )
        if load:
            problems.append("La nouvelle ressource serait sur-allouée")
    return SimulationResult(
        task_id,
        baseline.tasks[task_id].ef,
        baseline.tasks[task_id].ef,
        baseline.date_fin_projet,
        baseline.date_fin_projet,
        0,
        [],
        [],
        assignment.ressource_id if assignment else None,
        new_resource_id,
        not problems,
        problems,
    )


def compute_minimal_delay_to_avoid_conflict(
    task: AllocationTask,
    unavailability: UnavailablePeriod,
    calendar: WorkCalendar | None = None,
) -> int:
    """Calcule le plus petit décalage qui supprime un chevauchement ouvré."""

    calendar = calendar or WorkCalendar()
    duration = len(
        [
            day
            for day in (
                task.date_debut + timedelta(days=offset)
                for offset in range((task.date_fin - task.date_debut).days + 1)
            )
            if calendar.is_working_day(day)
        ]
    )
    delay = 0
    while True:
        start = calendar.add_working_days(task.date_debut, delay)
        end = (
            start
            if duration == 0
            else calendar.add_working_days(start, duration - 1)
        )
        if not compute_conflicts(start, end, [AllocationTask(
            task.id, task.nom, start, end, task.charge,
            task.est_critique, task.marge, task.statut, task.competences_requises,
        )], [unavailability], calendar):
            return delay
        delay += 1


def apply_proposal(db: Session, action_id: UUID, decideur_id: UUID) -> ActionAgent:
    """Applique et valide une proposition en attente du chef du projet."""

    action = db.get(ActionAgent, action_id)
    if action is None:
        raise ValueError("Action introuvable")
    if action.statut != AgentActionStatus.EN_ATTENTE:
        raise ValueError("Cette action a déjà été décidée")
    decider = db.get(Utilisateur, decideur_id)
    if decider is None or decider.role != UserRole.CHEF_PROJET or decider.id != action.projet.chef_id:
        raise PermissionError("Seul le chef du projet peut valider cette action")
    task = action.tache
    if task is None:
        raise ValueError("L'action ne référence aucune tâche")
    payload = action.payload or {}
    try:
        if action.type == AgentActionType.REAFFECTATION:
            new_resource_id = UUID(str(payload["new_resource_id"]))
            assignment = db.scalar(select(Affectation).where(Affectation.tache_id == task.id))
            if assignment is None:
                raise ValueError("La tâche n'est pas affectée")
            assignment.ressource_id = new_resource_id
        elif action.type == AgentActionType.DECALAGE:
            delay_days = int(payload["delay_days"])
            calendar = WorkCalendar()
            task.date_debut_prevue = calendar.add_working_days(
                task.date_debut_prevue, delay_days
            )
            task.date_fin_prevue = calendar.add_working_days(
                task.date_fin_prevue, delay_days
            )
            recompute_project_schedule(db, action.projet_id)
            _, project_start, tasks, dependencies, schedule_calendar = _project_data(
                db, task.id
            )
            simulated, _ = _schedule_with_delay(
                tasks,
                dependencies,
                project_start,
                schedule_calendar,
                task.id,
                delay_days,
            )
            for scheduled_task in tasks:
                scheduled = simulated[scheduled_task.id]
                scheduled_task.date_debut_prevue = scheduled.es
                scheduled_task.date_fin_prevue = scheduled.ef
                scheduled_task.marge = scheduled.marge
                scheduled_task.est_critique = scheduled.est_critique
        else:
            raise ValueError("Type d'action non applicable")
        action.statut = AgentActionStatus.ACCEPTEE
        action.decideur_id = decideur_id
        action.date_decision = datetime.utcnow()
        if action.type == AgentActionType.REAFFECTATION:
            recompute_project_schedule(db, action.projet_id)
        db.commit()
        db.refresh(action)
        return action
    except Exception:
        db.rollback()
        raise


class RescheduleService:
    """Façade de simulation et d'application des propositions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def simulate_delay(self, task_id: UUID, delay_days: int) -> SimulationResult:
        return simulate_delay(self.db, task_id, delay_days)

    def simulate_reassignment(
        self,
        task_id: UUID,
        new_resource_id: UUID,
    ) -> SimulationResult:
        return simulate_reassignment(self.db, task_id, new_resource_id)

    def apply_proposal(self, action_id: UUID, decideur_id: UUID) -> ActionAgent:
        return apply_proposal(self.db, action_id, decideur_id)
