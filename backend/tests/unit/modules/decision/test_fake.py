import pytest

from app.modules.decision.decision_model import DecisionRequest
from app.modules.decision.fake_decision_model import FakeDecisionModel
from tests.unit.modules.decision.helpers import REQUEST

pytestmark = pytest.mark.anyio


async def test_the_fake_answers_as_a_model_that_knows_nothing() -> None:
    decision = await FakeDecisionModel().decide(DecisionRequest.model_validate(REQUEST))

    answers = decision.model_dump()["answers"]
    assert decision.model == "fake"
    assert answers["angry"] == {"type": "noul", "noul": 0.5}
    assert answers["route"]["choice"] == "billing"
    assert answers["route"]["probabilities"] == {
        "billing": 1 / 3,
        "shipping": 1 / 3,
        "technical": 1 / 3,
    }
    assert answers["urgency"]["score"] == 1.5
    assert answers["urgency"]["legend"]["3"] == "right now"
    assert answers["urgency"]["confidence"] == 0.0


async def test_readiness_is_configurable_and_close_is_recorded() -> None:
    model = FakeDecisionModel(ready=False)

    assert await model.is_ready() is False
    await model.aclose()
    assert model.closed
