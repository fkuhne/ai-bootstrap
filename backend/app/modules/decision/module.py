"""The decision module, as the core plugs it in (docs/foundations.md#the-decision-model)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import settings_of
from app.core.modules import Module
from app.modules.decision.config import DecisionSettings
from app.modules.decision.dependencies import get_decision_model
from app.modules.decision.factory import create_decision_model
from app.modules.decision.router import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the decision model when the app starts, and close it when it stops."""
    settings = settings_of(DecisionSettings)
    model = create_decision_model(settings)
    logger.info(
        "Decision model %r (%s) at %s.", settings.model, settings.provider, settings.base_url
    )
    app.state.decision_model = model
    try:
        yield
    finally:
        await model.aclose()


async def is_ready(request: Request) -> bool:
    model = await get_decision_model(request)
    return await model.is_ready()


MODULE = Module(
    name="decision",
    router=router,
    settings=DecisionSettings,
    lifespan=lifespan,
    is_ready=is_ready,
)
