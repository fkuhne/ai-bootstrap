"""Store chunks in the RAG module the way an app would, and check that each call works.

Run it from the repo's root, with the stack up:

    docker compose run --rm rag-demo

It stores three chunks of two documents, lists what's stored, stores one of them again,
changed, which replaces it; searches them three ways, for an exact code and for a question in
other words; asks a question answered from them, citing them; then deletes both documents'
chunks. Its documents' names start with
`demo/`, so an app's own chunks are never touched. Each call is plain JSON over HTTP, printed
before it's sent, so the same calls work from any language: an app's ingestion makes them once
it has cut its documents into chunks.

It exits with status 1 when a call fails, or a count isn't what the calls should make. It uses
only the standard library, so it runs in a plain Python image.
"""

import sys
import time
from typing import Any

from demo import DemoError, Step, call, events, parameters, readiness, run, show_stream

RETURNS = "demo/returns.md"
SHIPPING = "demo/shipping.md"

CHUNKS: list[dict[str, Any]] = [
    {
        "id": "demo-returns-1",
        "source": RETURNS,
        "title": "Returns",
        "text": "Items can be returned within 30 days of delivery, unused and in their box.",
        "metadata": {"section": 1},
    },
    {
        "id": "demo-returns-2",
        "source": RETURNS,
        "title": "Refunds",
        "text": "Refunds reach the original payment method within five working days.",
        "metadata": {"section": 2},
    },
    {
        "id": "demo-shipping-1",
        "source": SHIPPING,
        "title": "Delivery times",
        "text": "Parcels arrive within three working days; error code E-4012 means a "
        "delivery address the carrier couldn't find.",
    },
]


def counts() -> dict[str, int]:
    """The demo's documents, and how many chunks each has stored."""
    listed = call("GET", "/api/rag/sources")["sources"]
    mine = {s["source"]: s["chunks"] for s in listed if s["source"].startswith("demo/")}
    print(f"  {len(listed)} source(s) stored; the demo's: {mine}")
    return mine


def expect(found: object, wanted: object, what: str) -> None:
    if found != wanted:
        raise DemoError(f"{what}: {found!r}, where {wanted!r} was expected")


def store() -> None:
    expect(call("PUT", "/api/rag/chunks", {"chunks": CHUNKS})["stored"], 3, "stored")


def listed() -> None:
    expect(counts(), {RETURNS: 2, SHIPPING: 1}, "the demo's sources")


def replace() -> None:
    changed = {**CHUNKS[1], "text": "Refunds reach the original payment method within a week."}
    expect(call("PUT", "/api/rag/chunks", {"chunks": [changed]})["stored"], 1, "stored")
    # Stored under its id again: it replaced the chunk, and added none.
    expect(counts(), {RETURNS: 2, SHIPPING: 1}, "the demo's sources")


def search(query: str, mode: str) -> list[dict[str, Any]]:
    body = {"query": query, "limit": 3, "mode": mode, "sources": [RETURNS, SHIPPING]}
    hits: list[dict[str, Any]] = call("POST", "/api/rag/search", body)["hits"]
    for hit in hits:
        print(
            f"    {hit['chunk']['id']}: score {hit['score']:.3f}, "
            f"similarity {hit['similarity']:.3f}"
        )
    return hits


def exact_code() -> None:
    """An exact code is found by its words: alone, or fused with the meaning, it comes first."""
    for mode in ("hybrid", "dense", "words"):
        hits = search("E-4012", mode)
        if mode != "dense":
            expect(hits[0]["chunk"]["id"] if hits else None, "demo-shipping-1", mode)


def other_words() -> None:
    """A question in other words than the chunk's is found by its meaning."""
    search("How long until I get my money back?", "hybrid")


def answer() -> None:
    """The sources come first, numbered; then the model's answer, citing them as [1]."""
    body = {
        "messages": [{"role": "user", "content": "How long do refunds take?"}],
        "parameters": parameters(),
        "limit": 3,
        "sources": [RETURNS, SHIPPING],
    }
    stream = events("/api/rag/ask/stream", body)
    first, data = next(stream)
    expect(first, "sources", "the first event")
    for source in data["sources"]:
        chunk = source["chunk"]
        print(f"  [{source['number']}] {chunk.get('title') or chunk['source']}: {chunk['text']}")
    done = show_stream(stream, time.perf_counter())
    expect(done["refused"], False, "refused")


def delete() -> None:
    expect(call("DELETE", f"/api/rag/sources/{RETURNS}")["deleted"], 2, "deleted")
    expect(counts(), {SHIPPING: 1}, "the demo's sources")
    expect(call("DELETE", f"/api/rag/sources/{SHIPPING}")["deleted"], 1, "deleted")
    expect(counts(), {}, "the demo's sources")


STEPS: list[Step] = [
    ("Are the embedding model and Qdrant ready?", readiness("rag")),
    ("Store three chunks of two documents", store),
    ("List what's stored", listed),
    ("Store a chunk again, changed: it replaces the one stored under its id", replace),
    ("Search for an exact code, three ways: hybrid, by meaning, by words", exact_code),
    ("Search for a question in other words", other_words),
    ("Answer from the chunks, citing them", answer),
    ("Delete each document's chunks", delete),
]


if __name__ == "__main__":
    sys.exit(run("RAG demo", STEPS))
