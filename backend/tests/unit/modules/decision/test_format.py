from typing import Any

import pytest
from pydantic import ValidationError

from app.modules.decision.decision_model import (
    ChoiceAnswer,
    Decision,
    DecisionRequest,
    NoulQuestion,
    ScoreAnswer,
)
from tests.unit.modules.decision.helpers import ANSWER, REQUEST


def test_a_request_takes_the_three_question_types() -> None:
    request = DecisionRequest.model_validate(REQUEST)

    assert isinstance(request.questions["angry"], NoulQuestion)
    assert request.model_dump(exclude_none=True) == REQUEST


def test_fields_a_provider_adds_pass_through() -> None:
    request = DecisionRequest.model_validate({**REQUEST, "model": "jev-latest"})
    decision = Decision.model_validate({**ANSWER, "usage": {**ANSWER["usage"], "cost": 0.0001}})

    assert request.model_dump()["model"] == "jev-latest"
    assert decision.model_dump()["usage"]["cost"] == 0.0001


@pytest.mark.parametrize(
    "questions",
    [
        {},
        {"q": {"type": "maybe", "instructions": "?"}},
        {"q": {"type": "choice", "instructions": "?", "criteria": {"only": None}}},
        {"q": {"type": "score", "instructions": "?", "criteria": ["one"]}},
        {"q": {"type": "score", "instructions": "?", "criteria": [str(n) for n in range(11)]}},
    ],
)
def test_malformed_questions_are_refused(questions: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DecisionRequest.model_validate({"state": "text", "questions": questions})


def test_an_answer_is_read_by_its_type() -> None:
    decision = Decision.model_validate(ANSWER)

    assert isinstance(decision.answers["route"], ChoiceAnswer)
    assert isinstance(decision.answers["urgency"], ScoreAnswer)
    assert decision.usage is not None
    assert decision.usage.input_tokens == 239
