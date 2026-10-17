"""The /api/decide endpoint: typed questions about a state, answered with probabilities."""

from fastapi import APIRouter, status

from app.core.errors import described
from app.modules.decision.decision_model import Decision, DecisionRequest
from app.modules.decision.dependencies import DecisionModelDep

router = APIRouter(prefix="/decide", tags=["decision"])

RESPONSES = described(
    {
        status.HTTP_429_TOO_MANY_REQUESTS: "The decision endpoint is rate-limiting",
        status.HTTP_502_BAD_GATEWAY: "The decision endpoint refused the request",
        status.HTTP_503_SERVICE_UNAVAILABLE: "The decision endpoint is unreachable or overloaded",
        status.HTTP_504_GATEWAY_TIMEOUT: "The decision endpoint didn't answer in time",
    }
)


@router.post(
    "",
    summary="Answer typed questions about a state",
    description="Sends the state and the questions to the decision model, in the System One "
    "format: `noul` questions are answered with the probability of yes, `choice` questions "
    "with each option's probability, and `score` questions with the expected level on their "
    "scale. The answers come back under the questions' names.",
    responses=RESPONSES,
)
async def decide(body: DecisionRequest, model: DecisionModelDep) -> Decision:
    return await model.decide(body)
