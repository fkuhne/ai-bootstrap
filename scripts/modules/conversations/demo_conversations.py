"""Call the conversations module the way an app would, and check that each call works.

Run it from the repo's root, with the stack up:

    docker compose run --rm conversations-demo

It starts a conversation the backend stores, asks in it twice, once whole and once streamed,
so the second question is answered with the first in its history; then reads it back, finds
it in the user's list, and deletes it. The conversations belong to the user id each call
sends in `X-User-Id`; a browser keeps one, and the demo makes a fresh one. Each call is plain
JSON over HTTP, printed before it's sent, so the same calls work from any language.
CHAT_DEMO_PARAMETERS, a JSON object, adds generation parameters to every question.

It exits with status 1 when a call fails. It checks that the backend answers and stores, not
what the model says. It uses only the standard library, so it runs in a plain Python image.
"""

import json
import sys
import time
import uuid
from typing import Any

from demo import (
    DemoError,
    Step,
    call,
    events,
    parameters,
    readiness,
    run,
    send,
    show_answer,
    show_stream,
)

# Whose stored conversations these are.
USER = {"X-User-Id": str(uuid.uuid4())}


def ask_body(content: str) -> dict[str, Any]:
    return {"content": content, "parameters": parameters()}


def stored_conversation() -> None:
    """The backend keeps this conversation: each question carries only itself."""
    path = f"/api/conversations/{call('POST', '/api/conversations', headers=USER)['id']}"
    started = time.perf_counter()
    turn = call("POST", f"{path}/messages", ask_body("My name is Ada."), USER)
    show_answer({**turn["answer"], **turn["answer"]["details"]}, time.perf_counter() - started)
    done = show_stream(
        events(f"{path}/messages/stream", ask_body("What is my name?"), USER),
        time.perf_counter(),
    )
    opened = call("GET", path, headers=USER)
    print(f"  title: {opened['title']!r}, {len(opened['messages'])} messages stored")
    if [m["id"] for m in opened["messages"][2:]] != [done["question_id"], done["answer_id"]]:
        raise DemoError("the stored conversation doesn't end with the streamed turn")
    with send("GET", "/api/conversations", headers=USER) as response:
        listed = json.load(response)
    print(f"  the user's list: {len(listed)} conversation(s)")
    if opened["id"] not in [c["id"] for c in listed]:
        raise DemoError("the conversation isn't in the user's list")
    with send("DELETE", path, headers=USER) as response:
        print(f"  deleted: HTTP {response.status}")


STEPS: list[Step] = [
    ("Are the LLM and the database ready?", readiness("llm", "conversations")),
    (
        "A conversation the backend stores: started, asked in twice, read back, listed, deleted",
        stored_conversation,
    ),
]


if __name__ == "__main__":
    sys.exit(run("Conversations demo", STEPS))
