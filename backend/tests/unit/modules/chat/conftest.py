"""The chat module's tests run against an app with the module in it."""

import pytest
from fastapi import FastAPI

from app.main import create_app
from app.modules.chat import MODULE


@pytest.fixture
def app() -> FastAPI:
    """The core and the chat module, in place of the core alone."""
    return create_app(modules=[MODULE])
