"""Ask the decision model through the backend, the way an app would, and check each answer.

Run it from the repo's root, with the stack up:

    docker compose run --rm decision-demo
    docker compose run --rm decision-demo "Your own text"

It asks three typed questions about a customer's message, or about your own text: whether
the customer is angry (noul, yes or no), which team should handle it (choice), and how
urgent it is (score). First one at a time, then all three in one call, as an app routes a
message. Each call is plain JSON over HTTP, printed before it's sent, so the same calls work
from any language.

It exits with status 1 when a call fails, or when an answer has the wrong shape: a
probability outside 0 to 1, probabilities that don't add up to 1, a choice that isn't one of
the options. It checks the shape, never what the model decides. It uses only the standard
library, so it runs in a plain Python image.
"""

import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

# main() accepts only http and https, so opening this URL is safe (ruff's S310).
BACKEND_URL = (os.environ.get("BACKEND_URL") or "http://backend:8000").rstrip("/")
TIMEOUT_SECONDS = 120

TEXT = (
    "Customer message: I was charged twice for my order last week, nobody has answered "
    "my emails, and I want my money back today."
)

QUESTIONS: dict[str, dict[str, Any]] = {
    "angry": {"type": "noul", "instructions": "Is the customer angry?"},
    "team": {
        "type": "choice",
        "instructions": "Which team should handle this message?",
        "criteria": {
            "billing": "Payments, refunds and invoices",
            "shipping": "Deliveries and returns",
            "technical": "The website and the app",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this message?",
        "criteria": ["can wait", "this week", "today", "right now"],
    },
}


class DemoError(Exception):
    """A call failed, or an answer has the wrong shape."""


def call(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make one call, printing it first, and return its JSON; an HTTP error is a DemoError."""
    print(f"  {method} {path} {json.dumps(body) if body else ''}".rstrip())
    request = urllib.request.Request(  # noqa: S310
        f"{BACKEND_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            reply: dict[str, Any] = json.load(response)
            return reply
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise DemoError(f"HTTP {error.code}: {detail}") from error


def readiness() -> None:
    """The backend answers 503 while any of its checks fails; this demo needs only the
    decision model's."""
    print("  GET /api/health/ready")
    try:
        with urllib.request.urlopen(  # noqa: S310
            f"{BACKEND_URL}/api/health/ready", timeout=TIMEOUT_SECONDS
        ) as response:
            checks = json.load(response).get("checks", {})
    except urllib.error.HTTPError as error:
        if error.code != 503:
            detail = error.read().decode(errors="replace")[:500]
            raise DemoError(f"HTTP {error.code}: {detail}") from error
        checks = json.load(error).get("checks", {})
    print(f"  {checks}")
    if "decision" not in checks:
        raise DemoError("the decision module is off: DECISION_ENABLED is 0")
    if checks["decision"] != "ok":
        raise DemoError("the decision model isn't ready yet: try again in a minute")


def ask(text: str, names: list[str]) -> None:
    """Ask the named questions about the text, and show and check each answer."""
    body = {"state": text, "questions": {name: QUESTIONS[name] for name in names}}
    started = time.perf_counter()
    reply = call("POST", "/api/decide", body)
    seconds = time.perf_counter() - started
    answers = reply.get("answers") or {}
    for name in names:
        if name not in answers:
            raise DemoError(f"no answer to {name!r}")
        print(f"  {name}: {describe(QUESTIONS[name], answers[name])}")
    usage = reply.get("usage") or {}
    print(
        f"  model {reply.get('model')}, {usage.get('input_tokens', '?')} input tokens, "
        f"{seconds:.2f} s"
    )


def describe(question: dict[str, Any], answer: dict[str, Any]) -> str:
    """The answer in words, once its shape is checked."""
    kind = question["type"]
    if answer.get("type") != kind:
        raise DemoError(f"a {kind} question got a {answer.get('type')} answer")
    if kind == "noul":
        probability(answer["noul"])
        return f"yes at {answer['noul']:.3f}"
    if kind == "choice":
        options = set(question["criteria"])
        distribution(answer["probabilities"], options)
        if answer["choice"] not in options:
            raise DemoError(f"{answer['choice']!r} isn't one of the options")
        probability(answer["confidence"])
        chosen = answer["probabilities"][answer["choice"]]
        return f"{answer['choice']} at {chosen:.3f}, confidence {answer['confidence']:.3f}"
    levels = question["criteria"]
    indexes = {str(index) for index in range(len(levels))}
    distribution(answer["probabilities"], indexes)
    if set(answer["legend"]) != indexes or not 0 <= answer["score"] <= len(levels) - 1:
        raise DemoError(f"the score {answer['score']} doesn't fit the {len(levels)} levels")
    probability(answer["confidence"])
    nearest = levels[round(answer["score"])]
    return (
        f"{answer['score']:.2f} on 0 to {len(levels) - 1}, near {nearest!r}, "
        f"confidence {answer['confidence']:.3f}"
    )


def probability(value: float) -> None:
    if not 0 <= value <= 1:
        raise DemoError(f"{value} isn't a probability")


def distribution(probabilities: dict[str, float], keys: set[str]) -> None:
    """One probability per option or level, adding up to 1."""
    if set(probabilities) != keys:
        raise DemoError(f"probabilities for {sorted(probabilities)}, not {sorted(keys)}")
    for value in probabilities.values():
        probability(value)
    if not math.isclose(sum(probabilities.values()), 1, abs_tol=0.01):
        raise DemoError(f"the probabilities add up to {sum(probabilities.values()):.3f}")


def steps(text: str) -> list[tuple[str, Callable[[], None]]]:
    return [
        ("Is the decision model ready?", readiness),
        ("Yes or no (noul)", lambda: ask(text, ["angry"])),
        ("One of named options (choice)", lambda: ask(text, ["team"])),
        ("A level on a scale (score)", lambda: ask(text, ["urgency"])),
        ("All three in one call, as an app routes a message", lambda: ask(text, list(QUESTIONS))),
    ]


def main() -> int:
    if not BACKEND_URL.startswith(("http://", "https://")):
        print(f"FAILED: BACKEND_URL must be an http or https URL, not {BACKEND_URL!r}")
        return 1
    text = " ".join(sys.argv[1:]) or TEXT
    print(f"Decision demo against {BACKEND_URL}\n  text: {text}")
    for number, (title, step) in enumerate(steps(text), start=1):
        print(f"\n{number}. {title}")
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


if __name__ == "__main__":
    sys.exit(main())
