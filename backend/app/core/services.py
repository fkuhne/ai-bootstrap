"""What every adapter to an outside service shares: how long a readiness probe waits, and how a
failed answer becomes the core's errors, with the service's own reason
(docs/foundations.md#errors)."""

import json

from app.core.errors import (
    ServiceError,
    ServiceRateLimitedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)

# Short, so a readiness probe fails fast rather than waiting behind real requests, as on a
# server with one processing slot. It's tried once.
READINESS_TIMEOUT_SECONDS = 5.0

# The statuses a server answers while it's down, overloaded or still loading its model: worth
# trying again later. 529 is Anthropic's "overloaded".
DOWN = frozenset({502, 503, 504, 529})

# How much of a service's reason is kept.
REASON_CHARACTERS = 500


def unreachable(service: str) -> ServiceUnavailableError:
    return ServiceUnavailableError(f"{service} can't be reached.")


def timed_out(service: str) -> ServiceTimeoutError:
    return ServiceTimeoutError(f"{service} didn't answer in time.")


def status_error(service: str, status: int, body: object) -> ServiceError:
    """The error a failed answer is: rate-limited for a 429; unavailable while the server is
    down; any other status a refusal with its reason, such as llama.cpp's 500 for a text
    longer than its batch."""
    if status == 429:
        return ServiceRateLimitedError(f"{service} is rate-limiting requests.")
    if status in DOWN:
        return ServiceUnavailableError(f"{service} failed with status {status}{reason(body)}")
    return ServiceError(f"{service} refused the request with status {status}{reason(body)}")


def json_or_none(text: str) -> object:
    """A body as JSON, or None when it isn't JSON."""
    try:
        return json.loads(text)
    except ValueError:
        return None


def reason(body: object) -> str:
    """The service's own reason in an error's body, such as which field it refused: `: <reason>`,
    or `.` when it gives none. It reads OpenAI's `{"error": {"message": …}}`, a plain
    `{"error": …}` or `{"detail": …}`, and Qdrant's `{"status": {"error": …}}`."""
    found = _reason(body)
    if not isinstance(found, str) or not found.strip():
        return "."
    return f": {found.strip()[:REASON_CHARACTERS]}"


def _reason(body: object) -> object:
    if not isinstance(body, dict):
        return None
    for field in ("message", "detail"):
        if isinstance(body.get(field), str):
            return body[field]
    for field in ("error", "status"):
        if isinstance(body.get(field), dict):
            return _reason(body[field])
    return body.get("error")
