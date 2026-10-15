import json
from pathlib import Path

import pytest

from app.agent.validator import validate_explanation


CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "hallucination_cases.json").read_text()
)


@pytest.mark.parametrize("case", CASES, ids=[f"case-{index}" for index, _ in enumerate(CASES)])
def test_hallucination_cases(case: dict) -> None:
    result = validate_explanation(case["text"], case["results"])
    assert result.ok is case["valid"]


def test_invalid_cases_are_all_detected_and_valid_cases_have_no_false_rejects() -> None:
    invalid = [case for case in CASES if not case["valid"]]
    valid = [case for case in CASES if case["valid"]]
    assert sum(not validate_explanation(case["text"], case["results"]).ok for case in invalid) == len(invalid)
    assert sum(not validate_explanation(case["text"], case["results"]).ok for case in valid) == 0


def test_derived_sum_is_not_authorized() -> None:
    result = validate_explanation(
        "La durée cumulée est de 5 jours.",
        [{"premiere": 2}, {"seconde": 3}],
    )
    assert result.ok is False
    assert result.unverified_values == ["5 jours"]
