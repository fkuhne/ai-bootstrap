"""The core's errors: each answered with its status and its message, in a response or as a
stream's `error` event; and how a service's failed answer becomes one, with its reason."""

import json
import logging

import httpx2
import pytest
from fastapi import APIRouter, Request

from app.core.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    ServiceError,
    ServiceRateLimitedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    app_error_handler,
    described,
    error_event,
)
from app.core.modules import Module
from app.core.services import json_or_none, reason, status_error
from app.main import create_app
from tests.helpers import ExampleSettings

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (AppError("Broken."), 500),
        (NotFoundError("No such thing."), 404),
        (ConflictError("Taken."), 409),
        (ServiceError("Refused."), 502),
        (ServiceRateLimitedError("Slow down."), 429),
        (ServiceUnavailableError("Down."), 503),
        (ServiceTimeoutError("Slow."), 504),
    ],
)
async def test_each_error_is_answered_with_its_status_and_its_message(
    error: AppError, status: int
) -> None:
    router = APIRouter()

    @router.get("/fail")
    async def fail() -> None:
        raise error

    app = create_app(modules=[Module("failing", router, ExampleSettings)])
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fail")

    assert (response.status_code, response.json()) == (status, {"detail": str(error)})


async def test_a_5xx_s_cause_goes_to_the_log_and_not_to_the_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    try:
        raise OSError("Connection refused\nmore lines")
    except OSError as cause:
        error = ServiceUnavailableError("The database is unavailable.")
        error.__cause__ = cause

    with caplog.at_level(logging.WARNING, logger="app.core.errors"):
        response = await app_error_handler(Request({"type": "http"}), error)

    assert json.loads(bytes(response.body)) == {"detail": "The database is unavailable."}
    assert "The database is unavailable. Cause: Connection refused" in caplog.text
    assert "more lines" not in caplog.text


def test_a_stream_s_error_event_has_the_status_the_request_answers() -> None:
    event = error_event(NotFoundError("No conversation 7."))

    assert event.event == "error"
    assert event.data.model_dump() == {"status": 404, "detail": "No conversation 7."}


def test_failure_statuses_are_described_as_fastapi_documents_them() -> None:
    assert described({503: "Down"}) == {503: {"description": "Down"}}


@pytest.mark.parametrize(
    ("status", "kind", "message"),
    [
        (429, ServiceRateLimitedError, "The model is rate-limiting requests."),
        (502, ServiceUnavailableError, "The model failed with status 502: busy"),
        (503, ServiceUnavailableError, "The model failed with status 503: busy"),
        (504, ServiceUnavailableError, "The model failed with status 504: busy"),
        (529, ServiceUnavailableError, "The model failed with status 529: busy"),
        # llama.cpp's answer to a text longer than its batch: a refusal, not an outage.
        (500, ServiceError, "The model refused the request with status 500: busy"),
        (501, ServiceError, "The model refused the request with status 501: busy"),
        (400, ServiceError, "The model refused the request with status 400: busy"),
    ],
)
def test_a_failed_answer_is_unavailable_only_while_the_server_is_down(
    status: int, kind: type[ServiceError], message: str
) -> None:
    error = status_error("The model", status, {"error": {"message": "busy"}})

    assert type(error) is kind
    assert str(error) == message


@pytest.mark.parametrize(
    ("body", "found"),
    [
        ({"error": {"message": "Invalid API key"}}, ": Invalid API key"),
        ({"message": "Invalid API key", "status": "INVALID_ARGUMENT"}, ": Invalid API key"),
        ({"error": "not a decision model"}, ": not a decision model"),
        ({"detail": "Wrong field"}, ": Wrong field"),
        ({"status": {"error": "Wrong input"}, "time": 0.1}, ": Wrong input"),
        ({"status": "forbidden"}, "."),
        ({"error": {"message": "  "}}, "."),
        ("Not Found", "."),
        (None, "."),
    ],
)
def test_a_service_s_reason_is_read_from_the_shapes_services_give_it(
    body: object, found: str
) -> None:
    assert reason(body) == found


def test_a_reason_is_cut_to_500_characters() -> None:
    assert reason({"error": "x" * 600}) == ": " + "x" * 500


def test_a_body_that_isn_t_json_has_no_reason() -> None:
    assert json_or_none('{"error": "e"}') == {"error": "e"}
    assert json_or_none("<html>") is None
