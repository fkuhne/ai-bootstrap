"""Application factory. Run with `uvicorn app.main:app`."""

import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from app.core.config import AppSettings, settings_of
from app.core.errors import AppError, app_error_handler
from app.core.logging import configure_logging
from app.core.modules import Module
from app.core.router import router as modules_router
from app.core.schemas import ErrorEvent
from app.health.router import router as health_router
from app.llm.config import LLMSettings
from app.llm.factory import create_llm_client
from app.llm.llm_client import ChatMessage, ContentDelta, ReasoningDelta, StreamEnd
from app.llm.router import router as llm_router
from app.modules import MODULES

API_PREFIX = "/api"

# The data of the core's streamed events; each module adds its own. FastAPI can't infer them
# from a stream, so they're added to the schema, for the API's documentation and the web UI's
# generated types.
STREAM_EVENT_MODELS: tuple[type[BaseModel], ...] = (
    ReasoningDelta,
    ContentDelta,
    StreamEnd,
    ErrorEvent,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Create the long-lived clients at startup, the modules' included, and close them at
    shutdown."""
    llm_settings = settings_of(LLMSettings)
    llm_client = create_llm_client(llm_settings)
    logger.info(
        "Ready: model %r (%s) at %s.",
        llm_settings.model,
        llm_settings.provider,
        llm_settings.base_url,
    )
    app.state.llm_client = llm_client
    try:
        async with AsyncExitStack() as modules:
            for module in app.state.modules:
                if module.lifespan is not None:
                    await modules.enter_async_context(module.lifespan(app))
            yield
    finally:
        await llm_client.aclose()


def create_app(
    settings: AppSettings | None = None, modules: Sequence[Module] | None = None
) -> FastAPI:
    """Build the application: logging, API docs, routers, all under `/api`, and the core's
    errors, with the modules given, or by default those their settings turn on."""
    settings = settings or settings_of(AppSettings)
    if modules is None:
        modules = [module for module in MODULES if module.enabled()]
    configure_logging(settings.log_level)
    app = FastAPI(
        title=settings.name,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if settings.docs_enabled else None,
    )
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(llm_router, prefix=API_PREFIX)
    app.include_router(modules_router, prefix=API_PREFIX)
    app.add_exception_handler(AppError, app_error_handler)
    app.state.modules = tuple(modules)
    for module in modules:
        app.include_router(module.router, prefix=API_PREFIX)
    app.openapi = lambda: openapi_with_stream_events(app)  # type: ignore[method-assign]
    return app


def openapi_with_stream_events(app: FastAPI) -> dict[str, Any]:
    """FastAPI's OpenAPI schema, with the streamed events' models among its own, and the LLM
    port's message, which a page that talks to the model writes whichever modules are on. Built
    once."""
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        event_models = (
            *STREAM_EVENT_MODELS,
            *(model for module in app.state.modules for model in module.event_models),
        )
        _, events = models_json_schema(
            [(model, "serialization") for model in event_models] + [(ChatMessage, "validation")],
            ref_template="#/components/schemas/{model}",
        )
        models = schema.setdefault("components", {}).setdefault("schemas", {})
        for name, model in events.get("$defs", {}).items():
            # FastAPI's own version of a shared model wins. Ours is published as FastAPI publishes
            # its own, without null values, such as a default of None, which the web UI's type
            # generator would read as a field always present.
            models.setdefault(name, jsonable_encoder(model, exclude_none=True))
        app.openapi_schema = schema
    return app.openapi_schema


app = create_app()
