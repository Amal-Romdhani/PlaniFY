from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.affectation import Affectation
from app.models.enums import ResourceType, TaskStatus
from app.models.indisponibilite import Indisponibilite
from app.models.ressource import Ressource
from app.models.tache import Tache
from app.services.critical_path_service import WorkCalendar


@dataclass(frozen=True)
class UnavailablePeriod:
    """Plage sans motif d'indisponibilité."""

    date_debut: date
    date_fin: date


@dataclass(frozen=True)
class ResourceAvailability:
    """Disponibilité quotidienne et plages indisponibles."""

    resource_id: UUID
    days: dict[date, bool]
    unavailable_periods: list[UnavailablePeriod]


@dataclass(frozen=True)
class OverallocationPeriod:
    """Période continue de surcharge."""

    date_debut: date
    date_fin: date
    charge: float


@dataclass(frozen=True)
class Conflict:
    """Chevauchement d'une tâche avec une indisponibilité."""

    tache_id: UUID
    nom: str
    jours_impactes: int
    est_critique: bool
    marge: int
    plage_indisponible: UnavailablePeriod


@dataclass(frozen=True)
class Candidate:
    """Ressource pouvant remplacer une ressource affectée."""

    resource_id: UUID
    nom: str
    charge_restante: float
    competences: list[str]


@dataclass(frozen=True)
class AllocationTask:
    """Données minimales d'une tâche affectée."""

    id: UUID
    nom: str
    date_debut: date
    date_fin: date
    charge: float
    est_critique: bool = False
    marge: int = 0
    statut: TaskStatus = TaskStatus.A_FAIRE
    competences_requises: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AllocationResource:
    """Données minimales d'une ressource candidate."""

    id: UUID
    nom: str
    type: ResourceType
    competences: list[str]
    charge_max: float


def _working_days(start: date, end: date, calendar: WorkCalendar) -> list[date]:
    if end < start:
        return []
    result: list[date] = []
    current = start
    while current <= end:
        if calendar.is_working_day(current):
            result.append(current)
        current += timedelta(days=1)
    return result


def _overlap_days(
    first: date,
    last: date,
    unavailable: UnavailablePeriod,
    calendar: WorkCalendar,
) -> int:
    start = max(first, unavailable.date_debut)
    end = min(last, unavailable.date_fin)
    return len(_working_days(start, end, calendar))


def compute_resource_availability(
    resource_id: UUID,
    start: date,
    end: date,
    unavailable_periods: list[UnavailablePeriod],
    calendar: WorkCalendar | None = None,
) -> ResourceAvailability:
    """Calcule une disponibilité journalière sans exposer les motifs."""

    calendar = calendar or WorkCalendar()
    periods = sorted(
        (
            UnavailablePeriod(
                max(start, item.date_debut),
                min(end, item.date_fin),
            )
            for item in unavailable_periods
            if item.date_debut <= end and item.date_fin >= start
        ),
        key=lambda item: item.date_debut,
    )
    days = {
        day: not any(period.date_debut <= day <= period.date_fin for period in periods)
        for day in _working_days(start, end, calendar)
    }
    return ResourceAvailability(resource_id, days, periods)


def compute_resource_load(
    start: date,
    end: date,
    tasks: list[AllocationTask],
    calendar: WorkCalendar | None = None,
) -> dict[date, float]:
    """Additionne la charge des tâches actives pour chaque jour ouvré."""

    calendar = calendar or WorkCalendar()
    load = {day: 0.0 for day in _working_days(start, end, calendar)}
    for task in tasks:
        if task.statut == TaskStatus.TERMINEE:
            continue
        task_days = _working_days(max(start, task.date_debut), min(end, task.date_fin), calendar)
        for day in task_days:
            load[day] += task.charge
    return load


def compute_overallocation(
    start: date,
    end: date,
    charge_max: float,
    tasks: list[AllocationTask],
    calendar: WorkCalendar | None = None,
) -> list[OverallocationPeriod]:
    """Fusionne les jours ouvrés où la charge dépasse le maximum."""

    calendar = calendar or WorkCalendar()
    load = compute_resource_load(start, end, tasks, calendar)
    periods: list[OverallocationPeriod] = []
    for day in sorted(load):
        if load[day] <= charge_max:
            continue
        if periods and calendar.add_working_days(periods[-1].date_fin, 1) == day:
            previous = periods[-1]
            periods[-1] = OverallocationPeriod(
                previous.date_debut,
                day,
                max(previous.charge, load[day]),
            )
        else:
            periods.append(OverallocationPeriod(day, day, load[day]))
    return periods


def compute_conflicts(
    start: date,
    end: date,
    tasks: list[AllocationTask],
    unavailable_periods: list[UnavailablePeriod],
    calendar: WorkCalendar | None = None,
) -> list[Conflict]:
    """Détecte les chevauchements ouvrés sans exposer de motif."""

    calendar = calendar or WorkCalendar()
    conflicts: list[Conflict] = []
    for task in tasks:
        for period in unavailable_periods:
            impacted = _overlap_days(task.date_debut, task.date_fin, period, calendar)
            if max(start, task.date_debut) <= min(end, task.date_fin):
                impacted = len(_working_days(
                    max(start, task.date_debut, period.date_debut),
                    min(end, task.date_fin, period.date_fin),
                    calendar,
                ))
            if impacted:
                conflicts.append(Conflict(task.id, task.nom, impacted, task.est_critique, task.marge, period))
    return conflicts


def compute_replacement_candidates(
    task: AllocationTask,
    current_resource_id: UUID,
    period_start: date,
    period_end: date,
    resources: list[AllocationResource],
    unavailable_by_resource: dict[UUID, list[UnavailablePeriod]],
    tasks_by_resource: dict[UUID, list[AllocationTask]],
    calendar: WorkCalendar | None = None,
) -> list[Candidate]:
    """Sélectionne les ressources humaines compétentes et disponibles."""

    calendar = calendar or WorkCalendar()
    required = set(task.competences_requises)
    candidates: list[Candidate] = []
    period_days = set(_working_days(period_start, period_end, calendar))
    for resource in resources:
        if resource.id == current_resource_id or resource.type != ResourceType.HUMAINE:
            continue
        if not required.issubset(resource.competences):
            continue
        unavailable_days = {
            day
            for period in unavailable_by_resource.get(resource.id, [])
            for day in _working_days(period.date_debut, period.date_fin, calendar)
        }
        if period_days & unavailable_days:
            continue
        load = compute_resource_load(period_start, period_end, tasks_by_resource.get(resource.id, []), calendar)
        max_load = max(load.values(), default=0.0)
        remaining = resource.charge_max - max_load
        if remaining >= task.charge:
            candidates.append(Candidate(resource.id, resource.nom, remaining, resource.competences))
    return sorted(candidates, key=lambda item: (-item.charge_restante, str(item.resource_id)))


class ResourceAllocationService:
    """Accès DB et orchestration des calculs d'allocation."""

    def __init__(self, db: Session, calendar: WorkCalendar | None = None) -> None:
        self.db = db
        self.calendar = calendar or WorkCalendar()

    def _resource(self, resource_id: UUID) -> Ressource:
        resource = self.db.get(Ressource, resource_id)
        if resource is None:
            raise ValueError("Ressource introuvable")
        return resource

    def _unavailability(self, resource_id: UUID) -> list[UnavailablePeriod]:
        rows = self.db.scalars(select(Indisponibilite).where(Indisponibilite.ressource_id == resource_id)).all()
        return [UnavailablePeriod(row.date_debut, row.date_fin) for row in rows]

    def _tasks(self, resource_id: UUID) -> list[AllocationTask]:
        rows = self.db.execute(
            select(Tache, Affectation.charge_allouee)
            .join(Affectation, Affectation.tache_id == Tache.id)
            .where(Affectation.ressource_id == resource_id)
        ).all()
        return [
            AllocationTask(
                task.id, task.nom, task.date_debut_prevue, task.date_fin_prevue,
                float(charge), task.est_critique, task.marge, task.statut,
                task.competences_requises,
            )
            for task, charge in rows
        ]

    def get_resource_availability(self, resource_id: UUID, start: date, end: date) -> ResourceAvailability:
        self._resource(resource_id)
        return compute_resource_availability(resource_id, start, end, self._unavailability(resource_id), self.calendar)

    def compute_resource_load(self, resource_id: UUID, start: date, end: date) -> dict[date, float]:
        self._resource(resource_id)
        return compute_resource_load(start, end, self._tasks(resource_id), self.calendar)

    def detect_overallocation(self, resource_id: UUID, start: date, end: date) -> list[OverallocationPeriod]:
        resource = self._resource(resource_id)
        return compute_overallocation(start, end, float(resource.charge_max), self._tasks(resource_id), self.calendar)

    def detect_conflicts(self, resource_id: UUID, start: date, end: date, project_id: UUID | None = None) -> list[Conflict]:
        tasks = self._tasks(resource_id)
        if project_id is not None:
            task_ids = set(self.db.scalars(select(Tache.id).where(Tache.projet_id == project_id)).all())
            tasks = [task for task in tasks if task.id in task_ids]
        return compute_conflicts(start, end, tasks, self._unavailability(resource_id), self.calendar)

    def find_replacement_candidates(self, task_id: UUID, period: tuple[date, date]) -> list[Candidate]:
        task = self.db.get(Tache, task_id)
        if task is None:
            raise ValueError("Tâche introuvable")
        assignment = self.db.scalar(select(Affectation).where(Affectation.tache_id == task_id))
        current_resource_id = assignment.ressource_id if assignment else UUID(int=0)
        resources = self.db.scalars(select(Ressource)).all()
        unavailable = {
            resource.id: self._unavailability(resource.id) for resource in resources
        }
        tasks_by_resource = {
            resource.id: self._tasks(resource.id) for resource in resources
        }
        allocation_task = AllocationTask(
            task.id, task.nom, task.date_debut_prevue, task.date_fin_prevue,
            float(assignment.charge_allouee if assignment else 0),
            task.est_critique, task.marge, task.statut, task.competences_requises,
        )
        return compute_replacement_candidates(
            allocation_task, current_resource_id, period[0], period[1],
            [
                AllocationResource(resource.id, resource.nom, resource.type, resource.competences, resource.charge_max)
                for resource in resources
            ],
            unavailable,
            tasks_by_resource,
            self.calendar,
        )


def get_resource_availability(db: Session, resource_id: UUID, start: date, end: date) -> ResourceAvailability:
    return ResourceAllocationService(db).get_resource_availability(resource_id, start, end)


def compute_resource_load_for_db(db: Session, resource_id: UUID, start: date, end: date) -> dict[date, float]:
    return ResourceAllocationService(db).compute_resource_load(resource_id, start, end)


def detect_overallocation(db: Session, resource_id: UUID, start: date, end: date) -> list[OverallocationPeriod]:
    return ResourceAllocationService(db).detect_overallocation(resource_id, start, end)


def detect_conflicts(db: Session, resource_id: UUID, start: date, end: date, project_id: UUID | None = None) -> list[Conflict]:
    return ResourceAllocationService(db).detect_conflicts(resource_id, start, end, project_id)


def find_replacement_candidates(db: Session, task_id: UUID, period: tuple[date, date]) -> list[Candidate]:
    return ResourceAllocationService(db).find_replacement_candidates(task_id, period)
