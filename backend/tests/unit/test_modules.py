"""How the core wires a module: its routes, errors, start and close, and readiness."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
import pytest
from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel

from app.core.errors import AppError
from app.core.modules import Module
from app.llm.dependencies import get_llm_client
from app.llm.fake_llm_client import FakeLLMClient
from app.main import create_app
from tests.helpers import ExampleSettings, OffSettings

pytestmark = pytest.mark.anyio


class EchoError(AppError):
    """The test module's own error, with a status of its own."""

    status_code = 418


class EchoEvent(BaseModel):
    """The data of an event the test module would stream."""

    echoed: str


class EchoModule:
    """A module for the tests: one route, one error, and a record of its start and close."""

    def __init__(self, *, enabled: bool = True, ready: bool = True) -> None:
        self.events: list[str] = []
        self.ready = ready
        router = APIRouter(prefix="/echo")

        @router.get("/{word}")
        async def echo(word: str) -> dict[str, str]:
            if word == "fail":
                raise EchoError("The echo failed.")
            return {"echo": word}

        @asynccontextmanager
        async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
            self.events.append("started")
            yield
            self.events.append("closed")

        async def is_ready(_request: Request) -> bool:
            return self.ready

        self.module = Module(
            name="echo",
            router=router,
            settings=ExampleSettings if enabled else OffSettings,
            lifespan=lifespan,
            is_ready=is_ready,
            event_models=(EchoEvent,),
        )


def client_for(app: FastAPI) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://test")


async def test_a_module_s_routes_and_errors_are_wired_under_api() -> None:
    echo = EchoModule()
    app = create_app(modules=[echo.module])

    async with client_for(app) as client:
        answer = await client.get("/api/echo/hello")
        failure = await client.get("/api/echo/fail")

    assert answer.json() == {"echo": "hello"}
    assert (failure.status_code, failure.json()) == (418, {"detail": "The echo failed."})


async def test_only_the_modules_their_settings_turn_on_are_wired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    on, off = EchoModule(), EchoModule(enabled=False)
    off.module = Module(**{**vars(off.module), "name": "off"})
    monkeypatch.setattr("app.main.MODULES", (on.module, off.module))

    app = create_app()

    assert app.state.modules == (on.module,)


@pytest.mark.parametrize(("ready", "status"), [(True, "ok"), (False, "unavailable")])
async def test_readiness_checks_each_module(ready: bool, status: str) -> None:
    echo = EchoModule(ready=ready)
    app = create_app(modules=[echo.module])
    app.dependency_overrides[get_llm_client] = FakeLLMClient

    async with client_for(app) as client:
        response = await client.get("/api/health/ready")

    assert response.json()["checks"] == {"llm": "ok", "echo": status}
    assert response.status_code == (200 if ready else 503)


async def test_readiness_runs_its_checks_at_once() -> None:
    # Each check is ready only once all three have started: one after another, the first would
    # wait for the others in vain.
    started: list[str] = []
    everyone = asyncio.Event()

    def waiting(name: str) -> Module:
        async def is_ready(_request: Request) -> bool:
            started.append(name)
            if len(started) == 3:
                everyone.set()
            try:
                async with asyncio.timeout(1):
                    await everyone.wait()
            except TimeoutError:
                return False
            return True

        return Module(
            name=name,
            router=APIRouter(),
            settings=ExampleSettings,
            is_ready=is_ready,
        )

    app = create_app(modules=[waiting("one"), waiting("two"), waiting("three")])
    app.dependency_overrides[get_llm_client] = FakeLLMClient

    async with client_for(app) as client:
        response = await client.get("/api/health/ready")

    assert response.json()["checks"] == {"llm": "ok", "one": "ok", "two": "ok", "three": "ok"}


async def test_a_module_starts_with_the_app_and_closes_with_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    echo = EchoModule()
    app = create_app(modules=[echo.module])

    async with app.router.lifespan_context(app):
        assert echo.events == ["started"]

    assert echo.events == ["started", "closed"]


async def test_a_module_may_have_no_clients_and_no_readiness_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    bare = Module(
        name="bare",
        router=APIRouter(),
        settings=ExampleSettings,
    )
    app = create_app(modules=[bare])
    app.dependency_overrides[get_llm_client] = FakeLLMClient

    async with app.router.lifespan_context(app), client_for(app) as client:
        response = await client.get("/api/health/ready")

    assert response.json()["checks"] == {"llm": "ok"}


def test_a_module_s_streamed_events_are_in_the_api_s_schema() -> None:
    app = create_app(modules=[EchoModule().module])

    assert "EchoEvent" in app.openapi()["components"]["schemas"]


async def test_the_modules_that_are_on_are_listed_in_order() -> None:
    first, second = EchoModule().module, EchoModule().module
    second = Module(**{**vars(second), "name": "second"})
    app = create_app(modules=[first, second])

    async with client_for(app) as client:
        listed = (await client.get("/api/modules")).json()
    async with client_for(create_app(modules=())) as client:
        none = (await client.get("/api/modules")).json()

    assert listed == {"modules": [{"name": "echo"}, {"name": "second"}]}
    assert none == {"modules": []}
