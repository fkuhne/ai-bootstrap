"""The errors the API answers with their status and their message, which every domain raises
(docs/foundations.md#errors). A domain subclasses one only where a caller tells its own apart."""

import logging
from collections.abc import Mapping
from typing import Any, ClassVar

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.sse import ServerSentEvent

from app.core.schemas import ErrorEvent

logger = logging.getLogger(__name__)

# The statuses an endpoint answers on failure, each with what it means, for the API's
# documentation.
Responses = dict[int | str, dict[str, Any]]


class AppError(Exception):
    """An error the API answers with `status_code`, and its message as the detail."""

    status_code: ClassVar[int] = 500


class NotFoundError(AppError):
    """What the request names doesn't exist, or isn't this user's."""

    status_code = 404


class ConflictError(AppError):
    """The request conflicts with what's stored."""

    status_code = 409


class ServiceError(AppError):
    """A service the app calls failed, or refused the request: the message gives its reason."""

    status_code = 502


class ServiceRateLimitedError(ServiceError):
    """The service is limiting how often it's called."""

    status_code = 429


class ServiceUnavailableError(ServiceError):
    """The service can't be reached, or is down, overloaded or still starting."""

    status_code = 503


class ServiceTimeoutError(ServiceError):
    """The service didn't answer in time."""

    status_code = 504


async def app_error_handler(_request: Request, error: Exception) -> JSONResponse:
    """The error's status, with its message as the detail. A 5xx's cause, which the answer
    leaves out, goes to the log."""
    status = error.status_code if isinstance(error, AppError) else 500
    if status >= 500 and error.__cause__ is not None:
        logger.warning("%s Cause: %s", error, str(error.__cause__).splitlines()[0])
    return JSONResponse(status_code=status, content={"detail": str(error)})


def error_event(error: AppError) -> ServerSentEvent:
    """The `error` event that ends a stream the error stopped, with the status the same
    request answers unstreamed."""
    logger.warning("A streamed answer ended with an error: %s", error)
    return ServerSentEvent(
        event="error", data=ErrorEvent(status=error.status_code, detail=str(error))
    )


def described(statuses: Mapping[int, str]) -> Responses:
    """An endpoint's failure statuses, each with what it means, as FastAPI documents them."""
    return {status: {"description": text} for status, text in statuses.items()}
