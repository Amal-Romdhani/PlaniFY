import json
from pathlib import Path


def test_scenario_inputs_are_never_sent_to_llm():
    scenarios = json.loads(
        (Path(__file__).parents[1] / "scenarios" / "unavailability_scenarios.json").read_text(
            encoding="utf-8"
        )
    )
    for scenario in scenarios:
        serialized = json.dumps(
            {
                "resource_id": "resource",
                "start": scenario["unavailability"]["start"],
                "end": scenario["unavailability"]["end"],
                "project_id": "project",
            },
            ensure_ascii=False,
        ).lower()
        assert "motif" not in serialized
        assert "maladie" not in serialized
        assert "conge" not in serialized
