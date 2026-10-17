"""What a module gives the core, so it plugs in and comes out through one list,
`app.modules.MODULES` (docs/foundations.md#modules)."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from app.core.config import ModuleSettings, settings_of


@dataclass(frozen=True)
class Module:
    """A capability an app includes or leaves out. The core wires each one its switch turns
    on: its routes under `/api`, its clients' start and close, its readiness check, and its
    streamed events in the API's schema. Its errors are the core's (`app.core.errors`)."""

    # Also the name of its readiness check.
    name: str
    router: APIRouter
    # Its settings class, which holds its switch, `<NAME>_ENABLED`.
    settings: type[ModuleSettings]
    # Any other settings class it reads, such as the database's.
    more_settings: tuple[type[BaseSettings], ...] = ()
    # Starts its clients, keeping them on `app.state`, and closes them when the app stops.
    # None for a module without clients of its own.
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None = None
    # None for a module without a service of its own, which then has no readiness check.
    is_ready: Callable[[Request], Awaitable[bool]] | None = None
    # The models of the events its endpoints stream. FastAPI can't infer them from a stream,
    # so the API's schema lists them, for its documentation and the web UI's types.
    event_models: tuple[type[BaseModel], ...] = ()

    def enabled(self) -> bool:
        """Whether its switch has it on."""
        return settings_of(self.settings).enabled
