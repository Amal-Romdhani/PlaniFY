from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action_agent import ActionAgent
from app.models.affectation import Affectation
from app.models.alerte import Alerte
from app.models.enums import AgentActionStatus, MilestoneStatus, RiskLevel, TaskStatus
from app.models.indisponibilite import Indisponibilite
from app.models.jalon import Jalon
from app.models.projet import Projet
from app.models.ressource import Ressource
from app.models.tache import Tache
from app.schemas.dashboard import (
    DashboardAlert,
    DashboardMilestone,
    DashboardResourceLoad,
    DashboardResponse,
    DashboardRiskIndicators,
    DashboardTaskCounts,
)


def _working_days(start: date, end: date) -> list[date]:
    if end < start:
        return []
    return [
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() < 5
    ]


def _risk_level(late_critical: int, conflicts: int, overloaded: int) -> RiskLevel:
    """Seuils: faible=0; moyen=1 indicateur; élevé=2 indicateurs ou plus."""

    indicators = sum(value > 0 for value in (late_critical, conflicts, overloaded))
    if indicators >= 2 or late_critical >= 3 or conflicts >= 3 or overloaded >= 2:
        return RiskLevel.ELEVE
    if indicators == 1:
        return RiskLevel.MOYEN
    return RiskLevel.FAIBLE


def get_project_dashboard(db: Session, project_id: UUID) -> DashboardResponse:
    """Calcule les indicateurs déterministes d'un projet."""

    project = db.get(Projet, project_id)
    if project is None:
        raise LookupError("Projet introuvable")

    tasks = list(db.scalars(select(Tache).where(Tache.projet_id == project_id)).all())
    milestones = list(db.scalars(select(Jalon).where(Jalon.projet_id == project_id)).all())
    assignments = list(
        db.scalars(
            select(Affectation)
            .join(Tache, Affectation.tache_id == Tache.id)
            .where(Tache.projet_id == project_id)
        ).all()
    )
    resources = list(
        db.scalars(
            select(Ressource)
            .where(Ressource.id.in_({item.ressource_id for item in assignments}))
        ).all()
    ) if assignments else []
    task_by_id = {task.id: task for task in tasks}
    resource_by_id = {resource.id: resource for resource in resources}
    today = date.today()

    total_duration = sum(task.duree for task in tasks)
    progress = (
        sum(task.avancement * task.duree for task in tasks) / total_duration
        if total_duration
        else 0.0
    )
    counts = Counter(task.statut for task in tasks)
    upcoming = [
        DashboardMilestone.model_validate(item)
        for item in sorted(
            (item for item in milestones if today <= item.date <= today + timedelta(days=30)),
            key=lambda item: item.date,
        )
    ]
    late_milestones = [
        DashboardMilestone.model_validate(item)
        for item in sorted(
            (item for item in milestones if item.date < today and item.statut != MilestoneStatus.ATTEINT),
            key=lambda item: item.date,
        )
    ]

    period_end = today + timedelta(days=27)
    period_days = _working_days(today, period_end)
    loads: dict[UUID, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for assignment in assignments:
        task = task_by_id.get(assignment.tache_id)
        if task is None or task.statut == TaskStatus.TERMINEE:
            continue
        for day in _working_days(max(today, task.date_debut_prevue), min(period_end, task.date_fin_prevue)):
            loads[assignment.ressource_id][day] += assignment.charge_allouee

    resource_loads: list[DashboardResourceLoad] = []
    overloaded_ids: list[UUID] = []
    for resource in sorted(resources, key=lambda item: item.nom):
        max_daily_load = max((loads[resource.id].get(day, 0.0) for day in period_days), default=0.0)
        percentage = round(max_daily_load / resource.charge_max * 100, 2) if resource.charge_max else 0.0
        overloaded = max_daily_load > resource.charge_max
        if overloaded:
            overloaded_ids.append(resource.id)
        resource_loads.append(
            DashboardResourceLoad(
                resource_id=resource.id,
                nom=resource.nom,
                pourcentage_utilisation=percentage,
                charge_max=resource.charge_max,
                charge_max_journaliere=max_daily_load,
                est_suralouee=overloaded,
            )
        )

    conflicts = 0
    for assignment in assignments:
        task = task_by_id.get(assignment.tache_id)
        resource = resource_by_id.get(assignment.ressource_id)
        if not task or not resource:
            continue
        conflicts += sum(
            1
            for unavailable in resource.indisponibilites
            if max(today, task.date_debut_prevue) <= min(period_end, task.date_fin_prevue, unavailable.date_fin)
            and max(today, task.date_debut_prevue, unavailable.date_debut)
            <= min(period_end, task.date_fin_prevue, unavailable.date_fin)
            and any(
                unavailable.date_debut <= day <= unavailable.date_fin
                for day in _working_days(
                    max(today, task.date_debut_prevue),
                    min(period_end, task.date_fin_prevue),
                )
            )
        )
    late_critical = sum(
        task.est_critique and task.date_fin_prevue < today and task.avancement < 100
        for task in tasks
    )
    alerts = list(
        db.scalars(
            select(Alerte)
            .where(Alerte.projet_id == project_id, Alerte.resolue.is_(False))
            .order_by(Alerte.date_creation.desc())
        ).all()
    )
    pending_recommendations = db.scalar(
        select(func.count(ActionAgent.id))
        .where(
            ActionAgent.projet_id == project_id,
            ActionAgent.statut == AgentActionStatus.EN_ATTENTE,
        )
    )
    risk = _risk_level(late_critical, conflicts, len(overloaded_ids))
    return DashboardResponse(
        avancement_global=round(progress, 2),
        date_debut=project.date_debut,
        date_fin_prevue=project.date_fin,
        jours_restants=max((project.date_fin - today).days, 0),
        nb_taches=DashboardTaskCounts(
            a_faire=counts[TaskStatus.A_FAIRE],
            en_cours=counts[TaskStatus.EN_COURS],
            terminee=counts[TaskStatus.TERMINEE],
        ),
        jalons_a_venir=upcoming,
        jalons_en_retard=late_milestones,
        charge_par_ressource=resource_loads,
        ressources_suralouees=overloaded_ids,
        risques=DashboardRiskIndicators(
            taches_critiques_en_retard=late_critical,
            conflits_ouverts=conflicts,
            ressources_suralouees=len(overloaded_ids),
            niveau_global=risk,
        ),
        alertes_non_resolues=[
            DashboardAlert(
                id=item.id,
                type=item.type.value,
                niveau_risque=item.niveau_risque.value,
                message=item.message,
                date_creation=item.date_creation.isoformat(),
            )
            for item in alerts
        ],
        nb_recommandations_en_attente=pending_recommendations or 0,
    )
