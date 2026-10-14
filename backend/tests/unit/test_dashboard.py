from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

from app.models.enums import (
    AlertType,
    MilestoneStatus,
    RiskLevel,
    TaskStatus,
)
from app.services.dashboard_service import _risk_level, get_project_dashboard


def _scalars(items: list[object]) -> SimpleNamespace:
    return SimpleNamespace(all=lambda: items)


def test_dashboard_calculates_progress_milestones_load_and_alerts() -> None:
    project_id = uuid4()
    task_id = uuid4()
    resource_id = uuid4()
    today = date.today()
    project = SimpleNamespace(
        id=project_id,
        date_debut=today - timedelta(days=2),
        date_fin=today + timedelta(days=10),
    )
    task = SimpleNamespace(
        id=task_id,
        projet_id=project_id,
        duree=2,
        avancement=50,
        statut=TaskStatus.EN_COURS,
        est_critique=True,
        date_debut_prevue=today,
        date_fin_prevue=today + timedelta(days=1),
    )
    resource = SimpleNamespace(
        id=resource_id,
        nom="Alice",
        charge_max=8,
        indisponibilites=[],
    )
    assignment = SimpleNamespace(ressource_id=resource_id, tache_id=task_id, charge_allouee=4)
    milestone = SimpleNamespace(
        id=uuid4(), nom="Livraison", date=today + timedelta(days=3),
        statut=MilestoneStatus.A_VENIR,
    )
    alert = SimpleNamespace(
        id=uuid4(), type=AlertType.RETARD, niveau_risque=RiskLevel.MOYEN,
        message="Retard", date_creation=datetime.now(),
    )
    db = Mock()
    db.get.return_value = project
    db.scalars.side_effect = [
        _scalars([task]),
        _scalars([milestone]),
        _scalars([assignment]),
        _scalars([resource]),
        _scalars([alert]),
    ]
    db.scalar.return_value = 2

    result = get_project_dashboard(db, project_id)

    assert result.avancement_global == 50
    assert result.nb_taches.en_cours == 1
    assert len(result.jalons_a_venir) == 1
    assert result.charge_par_ressource[0].pourcentage_utilisation == 50
    assert result.nb_recommandations_en_attente == 2
    assert result.risques.niveau_global == RiskLevel.FAIBLE


def test_dashboard_marks_multiple_risks_as_high() -> None:
    assert _risk_level(1, 1, 0) == RiskLevel.ELEVE
    assert _risk_level(3, 0, 0) == RiskLevel.ELEVE
