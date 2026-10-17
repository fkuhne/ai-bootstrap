"""Store the RAG module's sample chunks, and check that each sample question finds its chunk.

Run it from the repo's root, with the stack up:

    docker compose run --rm rag-samples            # store them, keep them, and check
    docker compose run --rm rag-samples --delete   # delete them

The samples, in samples.json beside this script, are the help centre of a fictional shop: a
dozen chunks of five documents, all under samples/, so an app's own chunks are never touched.
They're stored afresh, each document's chunks deleted first, and kept, so the Documents page has
something to answer from. Then each sample question is searched for, hybrid, and must find its
chunk among the first three: some ask by an exact code, some in other words than the chunk's,
some by its own words. It prints each rank, and no model answers.

It exits with status 1 when a call fails, or a question doesn't find its chunk. It uses only the
standard library, so it runs in a plain Python image.
"""

import json
import sys
from pathlib import Path
from typing import Any

from demo import DemoError, Step, call, readiness, run

SAMPLES: dict[str, Any] = json.loads((Path(__file__).parent / "samples.json").read_text())
SOURCES = sorted({chunk["source"] for chunk in SAMPLES["chunks"]})

# A question passes when its chunk is among the first this many hits.
WITHIN = 3


def delete() -> None:
    for source in SOURCES:
        call("DELETE", f"/api/rag/sources/{source}")


def store() -> None:
    delete()
    stored = call("PUT", "/api/rag/chunks", {"chunks": SAMPLES["chunks"]})["stored"]
    if stored != len(SAMPLES["chunks"]):
        raise DemoError(f"{stored} chunks stored, of {len(SAMPLES['chunks'])}")


def check() -> None:
    """Each question's rank, and a failure if any misses."""
    misses = []
    for asked in SAMPLES["questions"]:
        body = {"query": asked["question"], "limit": WITHIN, "mode": "hybrid", "sources": SOURCES}
        hits = [hit["chunk"]["id"] for hit in call("POST", "/api/rag/search", body)["hits"]]
        rank = hits.index(asked["expected"]) + 1 if asked["expected"] in hits else None
        found = "MISSED" if rank is None else f"#{rank}"
        print(f"    {found}: {asked['question']!r}, {asked['asks']}")
        if rank is None:
            misses.append(asked["question"])
    if misses:
        raise DemoError(f"{len(misses)} question(s) didn't find their chunk: {misses}")


STEPS: list[Step] = [
    ("Are the embedding model and Qdrant ready?", readiness("rag")),
    (f"Store the {len(SAMPLES['chunks'])} sample chunks of {len(SOURCES)} documents", store),
    (f"Each sample question finds its chunk among the first {WITHIN}", check),
]

DELETE_STEPS: list[Step] = [("Delete the sample chunks", delete)]


if __name__ == "__main__":
    if sys.argv[1:] == ["--delete"]:
        sys.exit(run("RAG samples", DELETE_STEPS))
    sys.exit(run("RAG samples", STEPS))
