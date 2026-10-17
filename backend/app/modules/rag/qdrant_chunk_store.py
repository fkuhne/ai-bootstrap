"""Adapter from the chunk store port to Qdrant's REST API (Adapter): one collection, with a
dense vector per chunk and the BM25 weights Qdrant computes from its text."""

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import httpx2
from pydantic import JsonValue

from app.core.errors import ConflictError
from app.core.services import (
    READINESS_TIMEOUT_SECONDS,
    json_or_none,
    status_error,
    timed_out,
    unreachable,
)
from app.modules.rag.chunk_store import ChunkStore, Found, ModelIdentity, Query, StoredChunk
from app.modules.rag.chunks import Chunk, SourceSummary

# How the store is named in errors.
SERVICE = "Qdrant"

# Qdrant's ids are UUIDs or numbers: a chunk's is derived from the app's own id, the same each
# time, so storing it again replaces it.
CHUNK_IDS = uuid.UUID("46f0f190-8585-4ce7-b7fa-3ddef57c3cb4")

# The most sources a listing returns.
SOURCES_LIMIT = 10_000

# How many chunks each half of a hybrid search brings to be fused: this many per hit asked for,
# and at least the minimum. RRF, with Qdrant's own constant, fuses them by rank.
CANDIDATES_PER_HIT = 4
MIN_CANDIDATES = 20


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(CHUNK_IDS, chunk_id))


class QdrantChunkStore(ChunkStore):
    """Calls Qdrant's REST API. The `http` client carries the base URL, the key and the
    timeout; `bm25` holds the options Qdrant's BM25 takes, such as `language`, sent with every
    text."""

    def __init__(
        self,
        http: httpx2.AsyncClient,
        *,
        collection: str,
        bm25: Mapping[str, JsonValue] | None = None,
    ) -> None:
        self._http = http
        self._collection = f"collections/{collection}"
        self._name = collection
        self._bm25 = dict(bm25 or {})

    async def identity(self) -> ModelIdentity | None:
        found = await self._call("GET", self._collection, missing_ok=True)
        if found is None:
            return None
        metadata = found["result"]["config"].get("metadata") or {}
        try:
            return ModelIdentity(
                model=str(metadata["embedding_model"]),
                dimensions=int(metadata["dimensions"]),
                probe=[float(value) for value in metadata["probe"]],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ConflictError(
                f"The collection {self._name!r} wasn't made by this module: set "
                "RAG_COLLECTION to another name."
            ) from error

    async def create(self, identity: ModelIdentity) -> None:
        """The collection, then an index on `source`, for deleting and listing by it. Made
        meanwhile by another request, it's left as it is."""
        await self._call(
            "PUT",
            self._collection,
            json={
                "vectors": {"dense": {"size": identity.dimensions, "distance": "Cosine"}},
                "sparse_vectors": {"bm25": {"modifier": "idf"}},
                "metadata": {
                    "embedding_model": identity.model,
                    "dimensions": identity.dimensions,
                    "probe": identity.probe,
                },
            },
            conflict_ok=True,
        )
        await self._call(
            "PUT",
            f"{self._collection}/index?wait=true",
            json={"field_name": "source", "field_schema": "keyword"},
        )

    async def upsert(self, chunks: Sequence[StoredChunk]) -> None:
        points = [
            {
                "id": point_id(stored.chunk.id),
                "vector": {"dense": stored.vector, "bm25": self._bm25_of(stored.chunk)},
                "payload": stored.chunk.model_dump(mode="json"),
            }
            for stored in chunks
        ]
        await self._call("PUT", f"{self._collection}/points?wait=true", json={"points": points})

    async def delete_source(self, source: str) -> int:
        """Counted first, since Qdrant's delete doesn't say how many it removed."""
        where = {"must": [{"key": "source", "match": {"value": source}}]}
        counted = await self._call(
            "POST",
            f"{self._collection}/points/count",
            json={"filter": where, "exact": True},
            missing_ok=True,
        )
        count = 0 if counted is None else int(counted["result"]["count"])
        if count > 0:
            await self._call(
                "POST", f"{self._collection}/points/delete?wait=true", json={"filter": where}
            )
        return count

    async def sources(self) -> list[SourceSummary]:
        faceted = await self._call(
            "POST",
            f"{self._collection}/facet",
            json={"key": "source", "limit": SOURCES_LIMIT, "exact": True},
            missing_ok=True,
        )
        if faceted is None:
            return []
        # Qdrant keeps counting a source whose chunks were all deleted, at 0.
        hits = [hit for hit in faceted["result"]["hits"] if hit["count"] > 0]
        return sorted(
            (SourceSummary(source=hit["value"], chunks=hit["count"]) for hit in hits),
            key=lambda summary: summary.source,
        )

    async def search(self, query: Query) -> list[Found]:
        found = await self._call(
            "POST", f"{self._collection}/points/query", json=self._search(query), missing_ok=True
        )
        if found is None:
            return []
        return [
            Found(
                chunk=Chunk.model_validate(point["payload"]),
                score=float(point["score"]),
                vector=point["vector"]["dense"],
            )
            for point in found["result"]["points"]
        ]

    async def is_ready(self) -> bool:
        """Qdrant's own readiness: it answers once every collection is loaded."""
        try:
            response = await self._http.get("readyz", timeout=READINESS_TIMEOUT_SECONDS)
        except httpx2.TransportError:
            return False
        return response.is_success

    async def aclose(self) -> None:
        await self._http.aclose()

    def _bm25_of(self, chunk: Chunk) -> dict[str, Any]:
        """The text Qdrant weighs, its title first."""
        return self._bm25_text(f"{chunk.title}\n{chunk.text}" if chunk.title else chunk.text)

    def _bm25_text(self, text: str) -> dict[str, Any]:
        """A text for Qdrant's BM25, a chunk's or a question's, with the options set."""
        document: dict[str, Any] = {"text": text, "model": "qdrant/bm25"}
        if self._bm25:
            document["options"] = self._bm25
        return document

    def _search(self, query: Query) -> dict[str, Any]:
        """The query's body: one half alone, or both fused by rank. Each hit comes with its
        chunk and its dense vector, for its similarity to the question."""
        meaning = {"query": query.vector, "using": "dense"}
        words = {"query": self._bm25_text(query.text), "using": "bm25"}
        where = (
            {"filter": {"must": [{"key": "source", "match": {"any": list(query.sources)}}]}}
            if query.sources
            else {}
        )
        returned = {"limit": query.limit, "with_payload": True, "with_vector": ["dense"]}
        if query.mode == "hybrid":
            candidates = max(query.limit * CANDIDATES_PER_HIT, MIN_CANDIDATES)
            halves = [{**half, "limit": candidates, **where} for half in (meaning, words)]
            return {"prefetch": halves, "query": {"fusion": "rrf"}, **returned}
        return {**(meaning if query.mode == "dense" else words), **where, **returned}

    async def _call(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        missing_ok: bool = False,
        conflict_ok: bool = False,
    ) -> dict[str, Any] | None:
        """Qdrant's answer, or None for a missing collection or one already made, when those
        are expected; anything else that fails raises the core's errors."""
        try:
            response = await self._http.request(method, path, json=json)
        except httpx2.TimeoutException as error:
            raise timed_out(SERVICE) from error
        except httpx2.TransportError as error:
            raise unreachable(SERVICE) from error
        if (missing_ok and response.status_code == httpx2.codes.NOT_FOUND) or (
            conflict_ok and response.status_code == httpx2.codes.CONFLICT
        ):
            return None
        if response.is_error:
            raise status_error(SERVICE, response.status_code, json_or_none(response.text))
        answer: dict[str, Any] = response.json()
        return answer
