import json
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from app.models.enums import ResourceType, TaskStatus
from app.services.critical_path_service import WorkCalendar
from app.services.resource_allocation_service import (
    AllocationResource,
    AllocationTask,
    UnavailablePeriod,
    compute_conflicts,
    compute_overallocation,
    compute_resource_availability,
    compute_resource_load,
    compute_replacement_candidates,
)


SCENARIOS = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "scenarios.json").read_text()
)


def make_task(data: dict) -> AllocationTask:
    return AllocationTask(
        UUID(data["id"]),
        data["nom"],
        date.fromisoformat(data["start"]),
        date.fromisoformat(data["end"]),
        data["charge"],
        data["critical"],
        data["margin"],
        TaskStatus.A_FAIRE,
        data["skills"],
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[item["name"] for item in SCENARIOS])
def test_scenario_conflicts_and_candidates(scenario: dict) -> None:
    task = make_task(scenario["task"])
    periods = [
        UnavailablePeriod(date.fromisoformat(item["start"]), date.fromisoformat(item["end"]))
        for item in scenario["absences"]
    ]
    conflicts = compute_conflicts(task.date_debut, task.date_fin, [task], periods)
    assert len(conflicts) == scenario["expected_conflicts"]
    resources = [
        AllocationResource(
            UUID(item["id"]), item["name"], ResourceType(item["type"]),
            item["skills"], item["max"],
        )
        for item in scenario["resources"]
    ]
    unavailable = {
        UUID(resource_id): [
            UnavailablePeriod(date.fromisoformat(item["start"]), date.fromisoformat(item["end"]))
            for item in values
        ]
        for resource_id, values in scenario.get("candidate_absences", {}).items()
    }
    candidates = compute_replacement_candidates(
        task,
        UUID(int=999),
        task.date_debut,
        task.date_fin,
        resources,
        unavailable,
        {resource.id: [] for resource in resources},
    )
    assert [str(candidate.resource_id) for candidate in candidates] == scenario["expected_candidates"]


def test_availability_never_contains_reason() -> None:
    result = compute_resource_availability(
        UUID(int=1),
        date(2026, 1, 5),
        date(2026, 1, 9),
        [UnavailablePeriod(date(2026, 1, 7), date(2026, 1, 8))],
    )
    assert result.days[date(2026, 1, 6)] is True
    assert result.days[date(2026, 1, 7)] is False
    assert not hasattr(result, "motif")


def test_load_excludes_completed_tasks_and_detects_periods() -> None:
    tasks = [
        AllocationTask(UUID(int=1), "active", date(2026, 1, 5), date(2026, 1, 7), 5),
        AllocationTask(UUID(int=2), "done", date(2026, 1, 5), date(2026, 1, 7), 20, statut=TaskStatus.TERMINEE),
    ]
    load = compute_resource_load(date(2026, 1, 5), date(2026, 1, 9), tasks)
    assert load[date(2026, 1, 6)] == 5
    periods = compute_overallocation(date(2026, 1, 5), date(2026, 1, 9), 4, tasks)
    assert periods[0].date_debut == date(2026, 1, 5)
    assert periods[0].date_fin == date(2026, 1, 7)
