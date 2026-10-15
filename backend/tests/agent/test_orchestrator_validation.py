from app.agent.orchestrator import AgentOrchestrator

from .test_orchestrator import FakeLLMClient, _fixture


def _final(text: str) -> dict:
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}


def test_invalid_explanation_is_regenerated(db_session):
    _, _, absence = _fixture(db_session)
    fake = FakeLLMClient([_final("Le retard est de 4 jours."), _final("Aucun conflit n'existe.")])

    result = AgentOrchestrator(fake).run(db_session, absence.id)

    assert result.validation_status == "REGENERE"
    assert result.final_response == "Aucun conflit n'existe."
    assert len(fake.calls) == 2


def test_two_invalid_explanations_use_digit_free_fallback(db_session):
    _, _, absence = _fixture(db_session)
    fake = FakeLLMClient([_final("Le retard est de 4 jours."), _final("Le retard est de 5 jours.")])

    result = AgentOrchestrator(fake).run(db_session, absence.id)

    assert result.validation_status == "REPLI"
    assert result.final_response == "L'analyse automatique ne peut pas être validée. Une validation humaine est requise."
    assert not any(character.isdigit() for character in result.final_response)
