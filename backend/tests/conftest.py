"""Shared fixtures. Route tests use an async client (httpx2 over ASGI)."""

import os
from collections.abc import AsyncIterator, Iterator

import httpx2
import pytest
from fastapi import FastAPI
from pydantic_settings import BaseSettings

from app.core.config import AppSettings, forget_settings
from app.llm.config import LLMSettings
from app.llm.dependencies import get_llm_client
from app.llm.llm_client import LLMClient
from app.main import create_app
from app.modules import MODULES
from tests.helpers import UseLLM

# The settings classes the backend reads, the core's and each module's, and their prefixes.
SETTINGS: tuple[type[BaseSettings], ...] = (
    AppSettings,
    LLMSettings,
    *(cls for module in MODULES for cls in (module.settings, *module.more_settings)),
)
SETTINGS_PREFIXES = tuple(cls.model_config["env_prefix"] for cls in SETTINGS)


@pytest.fixture(autouse=True)
def hermetic_settings(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Unit tests start from the defaults, whatever the shell or CI exports.

    Integration tests keep the environment, so `LLM_BASE_URL` can point them elsewhere.
    """
    if request.node.get_closest_marker("integration") is None:
        for name in list(os.environ):
            if name.startswith(SETTINGS_PREFIXES):
                monkeypatch.delenv(name)
    forget_settings()
    yield
    forget_settings()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def app() -> FastAPI:
    """The core alone: each module's tests build an app with their module, so the core's
    tests pass whichever modules an app keeps."""
    return create_app(modules=())


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def use_llm(app: FastAPI) -> UseLLM:
    """Make the app's routes use the given LLM client, as the lifespan would."""

    def use(llm: LLMClient) -> None:
        app.dependency_overrides[get_llm_client] = lambda: llm

    return use
