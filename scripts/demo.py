"""What the modules' demos share: calls to the backend as an app makes them, each printed before
it's sent so the same calls work from any language, and an LLM's answers shown as they arrive.

It uses only the standard library, so the demos run in a plain Python image. Their Compose
services put this folder on PYTHONPATH.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

# run() accepts only http and https, so opening this URL is safe (ruff's S310).
BACKEND_URL = (os.environ.get("BACKEND_URL") or "http://backend:8000").rstrip("/")
TIMEOUT_SECONDS = 600

# A data URL's content, shortened when a call is printed.
DATA_URL = re.compile(r"(data:[\w/.+-]+;base64,)[A-Za-z0-9+/=]+")

Step = tuple[str, Callable[[], None]]


class DemoError(Exception):
    """A call that failed, with the status and what the backend said."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def parameters() -> dict[str, Any]:
    """The generation parameters CHAT_DEMO_PARAMETERS adds to each question, as JSON."""
    try:
        value = json.loads(os.environ.get("CHAT_DEMO_PARAMETERS") or "{}")
    except ValueError as error:
        raise DemoError(f"CHAT_DEMO_PARAMETERS isn't valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise DemoError("CHAT_DEMO_PARAMETERS must be a JSON object, such as {}")
    return value


def send(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """Make one call and return the open response; an HTTP error becomes a DemoError."""
    shown = DATA_URL.sub(r"\1...", json.dumps(body)) if body else ""
    print(f"  {method} {path} {shown}".rstrip())
    request = urllib.request.Request(  # noqa: S310
        f"{BACKEND_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)  # noqa: S310
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise DemoError(f"HTTP {error.code}: {detail}", error.code) from error


def call(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    with send(method, path, body, headers) as response:
        reply: dict[str, Any] = json.load(response)
        return reply


def events(
    path: str, body: dict[str, Any], headers: dict[str, str] | None = None
) -> Iterator[tuple[str, dict[str, Any]]]:
    """The server-sent events of a streamed call, as (event, data), as they arrive."""
    with send("POST", path, body, headers) as response:
        event = "message"
        for raw in response:
            line = raw.decode().rstrip("\r\n")
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                yield event, json.loads(line.removeprefix("data: "))
                event = "message"


def readiness(*needed: str) -> Callable[[], None]:
    """A step that checks the backend is ready for a demo: the named checks must be ok. The
    backend answers 503 while any of its checks fails, so a module's demo reads the checks
    either way, and looks only at those it needs."""

    def step() -> None:
        print("  GET /api/health/ready")
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"{BACKEND_URL}/api/health/ready", timeout=TIMEOUT_SECONDS
            ) as response:
                checks = json.load(response)["checks"]
        except urllib.error.HTTPError as error:
            if error.code != 503:
                detail = error.read().decode(errors="replace")[:500]
                raise DemoError(f"HTTP {error.code}: {detail}", error.code) from error
            checks = json.load(error)["checks"]
        print(f"  {checks}")
        missing = [name for name in needed if checks.get(name) != "ok"]
        if missing:
            raise DemoError(f"not ready: {', '.join(missing)}; try again in a minute")

    return step


def show_answer(reply: dict[str, Any], seconds: float) -> None:
    """Print a whole answer, which must hold an answer or reasoning."""
    content, reasoning = reply.get("content") or "", reply.get("reasoning") or ""
    if reasoning:
        print(f"  reasoning: {len(reasoning)} characters before the answer")
    print(f"  answer:    {content.strip() or '(empty)'}")
    usage = reply.get("usage") or {}
    print(
        f"  model {reply.get('model')}, finish {reply.get('finish_reason')}, "
        f"{usage.get('completion_tokens', '?')} tokens, {seconds:.1f} s"
    )
    if not (content or reasoning).strip():
        raise DemoError("the answer is empty")


def show_stream(stream: Iterator[tuple[str, dict[str, Any]]], started: float) -> dict[str, Any]:
    """Print a streamed answer as it arrives, and return its `done` event's data."""
    reasoning, answered, done = 0, False, None
    for event, data in stream:
        if event == "reasoning":
            reasoning += len(data["text"])
        elif event == "token":
            if not answered:
                if reasoning:
                    print(f"  reasoning: {reasoning} characters before the answer")
                print("  answer:    ", end="", flush=True)
                answered = True
            print(data["text"], end="", flush=True)
        elif event == "done":
            done = data
        elif event == "error":
            raise DemoError(f"the stream ended with HTTP {data['status']}: {data['detail']}")
    print()
    if done is None:
        raise DemoError("the stream ended without its done event")
    usage = done.get("usage") or {}
    print(
        f"  model {done.get('model')}, finish {done.get('finish_reason')}, "
        f"{usage.get('completion_tokens', '?')} tokens, {time.perf_counter() - started:.1f} s"
    )
    return done


def run(title: str, steps: list[Step]) -> int:
    """Run the steps in order, numbered; stop at the first that fails. Returns the exit
    status: 1 when a step failed."""
    if not BACKEND_URL.startswith(("http://", "https://")):
        print(f"FAILED: BACKEND_URL must be an http or https URL, not {BACKEND_URL!r}")
        return 1
    print(f"{title} against {BACKEND_URL}")
    for number, (step_title, step) in enumerate(steps, start=1):
        print(f"\n{number}. {step_title}")
        try:
            step()
        except DemoError as error:
            print(f"FAILED: {error}")
            return 1
        except urllib.error.URLError as error:
            print(f"FAILED: can't reach the backend: {error.reason}")
            return 1
    print("\nOK")
    return 0
