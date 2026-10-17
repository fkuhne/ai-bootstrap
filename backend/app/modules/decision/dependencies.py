"""FastAPI dependencies of the decision module."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.modules.decision.decision_model import DecisionModel


async def get_decision_model(request: Request) -> DecisionModel:
    """The decision model the module's lifespan created. Tests override this."""
    return cast(DecisionModel, request.app.state.decision_model)


DecisionModelDep = Annotated[DecisionModel, Depends(get_decision_model)]
