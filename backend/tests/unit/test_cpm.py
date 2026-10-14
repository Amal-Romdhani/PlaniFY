from datetime import date
from time import perf_counter
from uuid import UUID

import pytest

from app.services.critical_path_service import (
    CPMResult,
    CycleError,
    Dep,
    TaskNode,
    WorkCalendar,
    compute_cpm,
)


START = date(2026, 1, 5)  # lundi


def node(number: int, duration: int) -> TaskNode:
    return TaskNode(UUID(int=number), duration)


def test_single_task() -> None:
    result = compute_cpm([node(1, 3)], [], START, WorkCalendar())
    task = result.tasks[UUID(int=1)]
    # ES lundi, EF mercredi, LS lundi, LF mercredi, marge 0.
    assert task.es == date(2026, 1, 5)
    assert task.ef == date(2026, 1, 7)
    assert task.marge == 0
    assert result.critical_path == [UUID(int=1)]
    assert result.duree_totale == 3


def test_linear_chain() -> None:
    tasks = [node(1, 2), node(2, 3), node(3, 1)]
    dependencies = [Dep(UUID(int=1), UUID(int=2)), Dep(UUID(int=2), UUID(int=3))]
    result = compute_cpm(tasks, dependencies, START, WorkCalendar())
    # A: lun-mar, B: mer-ven, C: lundi suivant; durée totale 6 jours ouvrés.
    assert result.date_fin_projet == date(2026, 1, 12)
    assert result.duree_totale == 6
    assert result.critical_path == [UUID(int=1), UUID(int=2), UUID(int=3)]


def test_parallel_branches_one_has_margin() -> None:
    tasks = [node(1, 2), node(2, 5), node(3, 1)]
    dependencies = [Dep(UUID(int=1), UUID(int=3))]
    result = compute_cpm(tasks, dependencies, START, WorkCalendar())
    # Branche B finit vendredi; C peut finir vendredi et A peut finir jeudi:
    # A et C ont respectivement deux et deux jours ouvrés de marge.
    assert result.tasks[UUID(int=2)].marge == 0
    assert result.tasks[UUID(int=1)].marge == 2
    assert result.tasks[UUID(int=3)].marge == 2


def test_diamond() -> None:
    tasks = [node(1, 2), node(2, 2), node(3, 3), node(4, 1)]
    dependencies = [
        Dep(UUID(int=1), UUID(int=2)),
        Dep(UUID(int=1), UUID(int=3)),
        Dep(UUID(int=2), UUID(int=4)),
        Dep(UUID(int=3), UUID(int=4)),
    ]
    result = compute_cpm(tasks, dependencies, START, WorkCalendar())
    # A lun-mar, B mer-jeu, C mer-ven, D lundi: le chemin critique passe par C.
    assert result.critical_path == [UUID(int=1), UUID(int=3), UUID(int=4)]
    assert result.tasks[UUID(int=2)].marge == 1


def test_equal_critical_paths() -> None:
    tasks = [node(1, 1), node(2, 2), node(3, 2), node(4, 1)]
    dependencies = [
        Dep(UUID(int=1), UUID(int=2)),
        Dep(UUID(int=1), UUID(int=3)),
        Dep(UUID(int=2), UUID(int=4)),
        Dep(UUID(int=3), UUID(int=4)),
    ]
    result = compute_cpm(tasks, dependencies, START, WorkCalendar())
    # Les deux branches durent deux jours après A: A, B, C et D sont critiques.
    assert result.critical_path == [
        UUID(int=1),
        UUID(int=2),
        UUID(int=3),
        UUID(int=4),
    ]


def test_independent_tasks() -> None:
    result = compute_cpm([node(1, 2), node(2, 5)], [], START, WorkCalendar())
    # A finit mardi, B vendredi; A peut commencer jeudi sans retarder le projet.
    assert result.tasks[UUID(int=1)].marge == 3
    assert result.tasks[UUID(int=2)].marge == 0


def test_cycle_raises_cycle_error() -> None:
    dependencies = [Dep(UUID(int=1), UUID(int=2)), Dep(UUID(int=2), UUID(int=1))]
    with pytest.raises(CycleError):
        compute_cpm([node(1, 1), node(2, 1)], dependencies, START, WorkCalendar())


def test_weekend_is_skipped() -> None:
    thursday = date(2026, 1, 8)
    result = compute_cpm([node(1, 3)], [], thursday, WorkCalendar())
    # Jeudi, vendredi, lundi: une tâche de trois jours finit le lundi.
    assert result.tasks[UUID(int=1)].ef == date(2026, 1, 12)


def test_holidays_are_skipped() -> None:
    calendar = WorkCalendar(holidays={date(2026, 1, 6)})
    result = compute_cpm([node(1, 2)], [], START, calendar)
    # Lundi puis mercredi, le mardi férié n'est pas consommé.
    assert result.tasks[UUID(int=1)].ef == date(2026, 1, 7)


def test_fifty_task_dag_is_fast() -> None:
    tasks = [node(number, number % 5 + 1) for number in range(1, 51)]
    dependencies = [
        Dep(UUID(int=source), UUID(int=target))
        for source in range(1, 50)
        for target in range(source + 1, min(50, source + 4))
    ]
    started = perf_counter()
    result = compute_cpm(tasks, dependencies, START, WorkCalendar())
    elapsed = perf_counter() - started
    assert isinstance(result, CPMResult)
    assert elapsed < 2
