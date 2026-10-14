from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dependance import Dependance
from app.models.projet import Projet
from app.models.tache import Tache


class CycleError(ValueError):
    """Le graphe de dépendances contient un cycle."""


@dataclass(frozen=True)
class TaskNode:
    """Nœud de calcul CPM."""

    id: UUID
    duree: int


@dataclass(frozen=True)
class Dep:
    """Dépendance fin-début entre deux tâches."""

    amont_id: UUID
    aval_id: UUID


@dataclass(frozen=True)
class WorkCalendar:
    """Calendrier lundi-vendredi avec jours fériés optionnels."""

    holidays: set[date] = field(default_factory=set)

    def is_working_day(self, value: date) -> bool:
        """Indique si une date est travaillée."""

        return value.weekday() < 5 and value not in self.holidays

    def add_working_days(self, value: date, n: int) -> date:
        """Avance ou recule de n jours ouvrés."""

        if n == 0:
            return value
        step = 1 if n > 0 else -1
        remaining = abs(n)
        current = value
        while remaining:
            current += timedelta(days=step)
            if self.is_working_day(current):
                remaining -= 1
        return current

    def working_days_between(self, first: date, second: date) -> int:
        """Retourne le nombre de déplacements ouvrés entre deux dates."""

        if first == second:
            return 0
        step = 1 if second > first else -1
        current = first
        result = 0
        while current != second:
            current = self.add_working_days(current, step)
            result += step
        return result


@dataclass(frozen=True)
class CPMTaskResult:
    """Dates et marge calculées pour une tâche."""

    es: date
    ef: date
    ls: date
    lf: date
    marge: int
    est_critique: bool


@dataclass(frozen=True)
class CPMResult:
    """Résultat complet de la méthode du chemin critique."""

    tasks: dict[UUID, CPMTaskResult]
    critical_path: list[UUID]
    date_fin_projet: date
    duree_totale: int


def _finish(start: date, duration: int, calendar: WorkCalendar) -> date:
    return start if duration == 0 else calendar.add_working_days(start, duration - 1)


def _start_from_finish(finish: date, duration: int, calendar: WorkCalendar) -> date:
    return finish if duration == 0 else calendar.add_working_days(finish, -(duration - 1))


def compute_cpm(
    tasks: list[TaskNode],
    dependencies: list[Dep],
    project_start: date,
    calendar: WorkCalendar,
) -> CPMResult:
    """Calcule le CPM sans accès à la base de données ni effet de bord."""

    task_by_id = {task.id: task for task in tasks}
    if len(task_by_id) != len(tasks):
        raise ValueError("Les identifiants de tâches doivent être uniques")
    successors: dict[UUID, list[UUID]] = defaultdict(list)
    predecessors: dict[UUID, list[UUID]] = defaultdict(list)
    indegree = {task.id: 0 for task in tasks}
    for dependency in dependencies:
        if dependency.amont_id not in task_by_id or dependency.aval_id not in task_by_id:
            raise ValueError("Une dépendance référence une tâche inconnue")
        if dependency.aval_id not in successors[dependency.amont_id]:
            successors[dependency.amont_id].append(dependency.aval_id)
            predecessors[dependency.aval_id].append(dependency.amont_id)
            indegree[dependency.aval_id] += 1

    queue = deque(sorted((task_id for task_id, degree in indegree.items() if degree == 0), key=str))
    topological_order: list[UUID] = []
    while queue:
        task_id = queue.popleft()
        topological_order.append(task_id)
        for successor in successors[task_id]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)
    if len(topological_order) != len(tasks):
        raise CycleError("Le graphe de dépendances est cyclique")

    es: dict[UUID, date] = {}
    ef: dict[UUID, date] = {}
    for task_id in topological_order:
        task = task_by_id[task_id]
        earliest_start = project_start
        if predecessors[task_id]:
            earliest_start = max(
                calendar.add_working_days(ef[parent], 1)
                for parent in predecessors[task_id]
            )
        es[task_id] = earliest_start
        ef[task_id] = _finish(earliest_start, task.duree, calendar)

    project_finish = max(ef.values(), default=project_start)
    lf: dict[UUID, date] = {}
    ls: dict[UUID, date] = {}
    for task_id in reversed(topological_order):
        task = task_by_id[task_id]
        latest_finish = project_finish
        if successors[task_id]:
            latest_finish = min(
                calendar.add_working_days(ls[child], -1)
                for child in successors[task_id]
            )
        lf[task_id] = latest_finish
        ls[task_id] = _start_from_finish(latest_finish, task.duree, calendar)

    results = {
        task_id: CPMTaskResult(
            es=es[task_id],
            ef=ef[task_id],
            ls=ls[task_id],
            lf=lf[task_id],
            marge=calendar.working_days_between(es[task_id], ls[task_id]),
            est_critique=es[task_id] == ls[task_id],
        )
        for task_id in topological_order
    }
    critical_path = [
        task_id for task_id in topological_order if results[task_id].est_critique
    ]
    return CPMResult(
        tasks=results,
        critical_path=critical_path,
        date_fin_projet=project_finish,
        duree_totale=calendar.working_days_between(project_start, project_finish) + (
            1 if tasks else 0
        ),
    )


def _load_project_cpm(db: Session, project_id: UUID) -> tuple[Projet, CPMResult]:
    project = db.get(Projet, project_id)
    if project is None:
        raise ValueError("Projet introuvable")
    tasks = list(db.scalars(select(Tache).where(Tache.projet_id == project_id)).all())
    task_ids = {task.id for task in tasks}
    dependencies = list(
        db.scalars(
            select(Dependance).where(
                Dependance.tache_amont_id.in_(task_ids),
                Dependance.tache_aval_id.in_(task_ids),
            )
        ).all()
    )
    result = compute_cpm(
        [TaskNode(id=task.id, duree=task.duree) for task in tasks],
        [Dep(amont_id=dep.tache_amont_id, aval_id=dep.tache_aval_id) for dep in dependencies],
        project.date_debut,
        WorkCalendar(),
    )
    return project, result


def recompute_project_schedule(db: Session, project_id: UUID) -> None:
    """Recalcule et persiste les dates et marges du projet."""

    project, result = _load_project_cpm(db, project_id)
    task_by_id = {
        task.id: task
        for task in db.scalars(select(Tache).where(Tache.projet_id == project_id)).all()
    }
    for task_id, computed in result.tasks.items():
        task = task_by_id[task_id]
        task.date_debut_prevue = computed.es
        task.date_fin_prevue = computed.ef
        task.marge = computed.marge
        task.est_critique = computed.est_critique
    project.date_fin = result.date_fin_projet


def get_project_schedule(db: Session, project_id: UUID) -> CPMResult:
    """Calcule le CPM d'un projet sans modifier la base."""

    _, result = _load_project_cpm(db, project_id)
    return result
