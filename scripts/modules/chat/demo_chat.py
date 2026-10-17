"""Call the chat module the way an app would, and check that each call works.

Run it from the repo's root, with the stack up:

    docker compose run --rm chat-demo
    docker compose run --rm chat-demo "Your own question"

In order, it shows readiness, a whole answer, a conversation with a system prompt and earlier
turns, an answer streamed as it's written, and a question about an image. The backend keeps
nothing: each call carries the conversation so far. Each call is plain JSON over HTTP, printed
before it's sent, so the same calls work from any language. CHAT_DEMO_PARAMETERS, a JSON
object, adds generation parameters to every request, such as {"temperature": 0.7} or
{"reasoning_effort": "none"}.

It exits with status 1 when a call fails. It checks that the backend answers, not what the
model says. It uses only the standard library, so it runs in a plain Python image.
"""

import base64
import sys
import time
from typing import Any

from demo import DemoError, Step, call, events, parameters, readiness, run, show_answer, show_stream
from media import red_square_png

QUESTION = " ".join(sys.argv[1:]) or "In two sentences, what is a large language model?"
IMAGE_URI = "data:image/png;base64," + base64.b64encode(red_square_png()).decode()


def chat_body(messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {"messages": messages, "parameters": parameters()}


def whole_answer() -> None:
    started = time.perf_counter()
    reply = call("POST", "/api/chat", chat_body([{"role": "user", "content": QUESTION}]))
    show_answer(reply, time.perf_counter() - started)


def conversation() -> None:
    """The backend keeps no state: each call carries the conversation so far."""
    messages = [
        {"role": "system", "content": "Answer in one short sentence."},
        {"role": "user", "content": "My name is Ada."},
        {"role": "assistant", "content": "Nice to meet you, Ada."},
        {"role": "user", "content": "What is my name?"},
    ]
    started = time.perf_counter()
    show_answer(call("POST", "/api/chat", chat_body(messages)), time.perf_counter() - started)


def streamed() -> None:
    body = chat_body([{"role": "user", "content": QUESTION}])
    show_stream(events("/api/chat/stream", body), time.perf_counter())


def image() -> None:
    """Content can be a list of parts: text, images, audio or video."""
    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "What color is this image? Answer with one word."},
            {"type": "image_url", "image_url": {"url": IMAGE_URI}},
        ],
    }
    started = time.perf_counter()
    try:
        reply = call("POST", "/api/chat", chat_body([message]))
    except DemoError as error:
        if error.status != 502:
            raise
        print(f"  skipped: the model refused the image ({error})")
        return
    show_answer(reply, time.perf_counter() - started)


STEPS: list[Step] = [
    ("Is the LLM ready?", readiness("llm")),
    ("A whole answer", whole_answer),
    ("A conversation: a system prompt and earlier turns", conversation),
    ("The same kind of answer, streamed as it's written", streamed),
    ("A question about an image", image),
]


if __name__ == "__main__":
    sys.exit(run("Chat demo", STEPS))
