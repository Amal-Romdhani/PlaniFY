from datetime import date
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models.action_agent import ActionAgent
from app.models.affectation import Affectation
from app.models.enums import (
    AgentActionStatus,
    AgentActionType,
    ProjectStatus,
    ResourceType,
    TaskStatus,
    UserRole,
)
from app.models.projet import Projet
from app.models.ressource import Ressource
from app.models.tache import Tache
from app.models.utilisateur import Utilisateur
from app.services.reschedule_service import (
    AllocationTask,
    UnavailablePeriod,
    apply_proposal,
    compute_minimal_delay_to_avoid_conflict,
    simulate_delay,
    simulate_reassignment,
)


def build_project(db_session):
    chef = Utilisateur(
        nom="Chef reschedule",
        email=f"{uuid4()}@example.com",
        mot_de_passe_hash=hash_password("password"),
        role=UserRole.CHEF_PROJET,
    )
    project = Projet(
        nom="Projet reschedule",
        date_debut=date(2026, 1, 5),
        date_fin=date(2026, 1, 16),
        statut=ProjectStatus.PLANIFIE,
        chef=chef,
    )
    first = Tache(
        projet=project,
        nom="Tâche marge",
        duree=2,
        date_debut_prevue=date(2026, 1, 5),
        date_fin_prevue=date(2026, 1, 6),
        statut=TaskStatus.A_FAIRE,
    )
    second = Tache(
        projet=project,
        nom="Tâche critique",
        duree=5,
        date_debut_prevue=date(2026, 1, 5),
        date_fin_prevue=date(2026, 1, 9),
        statut=TaskStatus.A_FAIRE,
    )
    resource = Ressource(
        nom="Ressource A",
        type=ResourceType.HUMAINE,
        competences=[],
        charge_max=8,
    )
    db_session.add_all([project, first, second, resource])
    db_session.flush()
    return chef, project, first, second, resource


def test_delay_simulation_does_not_write_and_reports_project_impact(db_session) -> None:
    _, _, first, _, resource = build_project(db_session)
    db_session.add(Affectation(ressource_id=resource.id, tache_id=first.id, charge_allouee=2))
    db_session.flush()
    before = (first.date_debut_prevue, first.date_fin_prevue)
    result = simulate_delay(db_session, first.id, 1)
    assert result.retard_projet_jours == 0
    assert result.ancienne_date_fin_tache != result.nouvelle_date_fin_tache
    assert (first.date_debut_prevue, first.date_fin_prevue) == before
    assert not db_session.dirty


def test_critical_delay_reports_exact_delay(db_session) -> None:
    _, _, _, critical, _ = build_project(db_session)
    result = simulate_delay(db_session, critical.id, 2)
    assert result.retard_projet_jours == 2


def test_reassignment_ok_and_impossible(db_session) -> None:
    _, _, first, _, current = build_project(db_session)
    replacement = Ressource(
        nom="Ressource B",
        type=ResourceType.HUMAINE,
        competences=[],
        charge_max=8,
    )
    db_session.add(replacement)
    db_session.flush()
    db_session.add(Affectation(ressource_id=current.id, tache_id=first.id, charge_allouee=2))
    db_session.flush()
    result = simulate_reassignment(db_session, first.id, replacement.id)
    assert result.reaffectation_possible is True
    assert result.retard_projet_jours == 0
    impossible = simulate_reassignment(db_session, first.id, uuid4())
    assert impossible.reaffectation_possible is False
    assert impossible.problemes


def test_minimal_delay_after_unavailability() -> None:
    task = AllocationTask(
        uuid4(),
        "Tâche",
        date(2026, 1, 5),
        date(2026, 1, 7),
        1,
    )
    delay = compute_minimal_delay_to_avoid_conflict(
        task,
        UnavailablePeriod(date(2026, 1, 6), date(2026, 1, 6)),
    )
    assert delay == 2


def test_apply_proposal_rejects_decided_action(db_session) -> None:
    chef, project, task, _, _ = build_project(db_session)
    action = ActionAgent(
        projet_id=project.id,
        tache_id=task.id,
        type=AgentActionType.DECALAGE,
        justification="Déjà décidée",
        payload={"delay_days": 1},
        statut=AgentActionStatus.ACCEPTEE,
    )
    db_session.add(action)
    db_session.flush()
    with pytest.raises(ValueError, match="déjà"):
        apply_proposal(db_session, action.id, chef.id)
