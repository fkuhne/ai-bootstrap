"""The committed OpenAPI schema, which the web UI's types come from
(docs/foundations.md#the-web-ui)."""

import json
import runpy
import sys
from pathlib import Path

import pytest

from app.main import create_app
from app.openapi import SCHEMA_FILE, main, render, schema


def test_the_committed_schema_is_the_apps() -> None:
    # If this fails, an endpoint or a model changed: run `python -m app.openapi` in
    # backend-checks, then `npm run api:types` in frontend-checks, and commit both files.
    assert SCHEMA_FILE.read_text(encoding="utf-8") == render(schema())


def test_the_schema_ignores_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "my-app")
    monkeypatch.setenv("APP_DOCS_ENABLED", "false")

    assert schema()["info"]["title"] == "ai-bootstrap"


def test_the_streamed_events_models_are_in_the_schema() -> None:
    models = schema()["components"]["schemas"]

    for name in ("ReasoningDelta", "ContentDelta", "StreamEnd", "ErrorEvent"):
        assert name in models
    # A model the events share with the endpoints keeps FastAPI's own description.
    assert models["Usage"] == create_app().openapi()["components"]["schemas"]["Usage"]


def test_the_schema_is_built_once() -> None:
    app = create_app()

    assert app.openapi() is app.openapi()


def test_main_writes_the_schema_where_it_is_asked(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"

    main([str(output)])

    assert json.loads(output.read_text(encoding="utf-8")) == schema()


def test_it_runs_as_a_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "openapi.json"
    monkeypatch.setattr(sys, "argv", ["openapi", str(output)])
    monkeypatch.delitem(sys.modules, "app.openapi")  # run it fresh, as `python -m` would

    runpy.run_module("app.openapi", run_name="__main__")

    assert output.exists()


def test_the_llm_s_message_is_in_the_schema_without_any_module() -> None:
    # The web UI's core types a message from it, whichever modules an app keeps.
    models = create_app(modules=()).openapi()["components"]["schemas"]

    assert {"ChatMessage", "TextPart", "ImagePart", "AudioPart", "VideoPart"} <= set(models)


def test_the_core_s_own_models_are_published_as_fastapi_publishes_its_own() -> None:
    # Without a module, nothing of FastAPI's covers the message's parts: an optional field must
    # still read as optional, with no default of null.
    models = create_app(modules=()).openapi()["components"]["schemas"]

    assert "default" not in models["ImageURL"]["properties"]["detail"]
    assert models["ImageURL"]["required"] == ["url"]
