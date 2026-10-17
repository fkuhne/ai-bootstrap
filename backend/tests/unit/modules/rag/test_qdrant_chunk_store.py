"""The adapter talks to a mock transport, answering as Qdrant 1.19 does: real HTTP parsing, no
network."""

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from app.core.errors import (
    ConflictError,
    ServiceError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from app.core.services import READINESS_TIMEOUT_SECONDS
from app.modules.rag.chunk_store import Found, ModelIdentity, Query, StoredChunk
from app.modules.rag.chunks import Chunk, Mode, SourceSummary
from app.modules.rag.qdrant_chunk_store import QdrantChunkStore, point_id

pytestmark = pytest.mark.anyio

IDENTITY = ModelIdentity(model="local", dimensions=2, probe=[0.6, 0.8])
RETURNS = Chunk(
    id="returns-1",
    source="help/returns.md",
    title="Returns",
    text="Items can be returned within 30 days.",
    metadata={"page": 1},
)

Answer = httpx2.Response | httpx2.TransportError


class FakeQdrant:
    """Answers each call by its method and path, the last answer repeated, and keeps them."""

    def __init__(self, answers: dict[str, Answer] | None = None) -> None:
        self.answers = answers or {}
        self.calls: list[tuple[str, str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path + (f"?{request.url.query.decode()}" if request.url.query else "")
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, body))
        answer = self.answers.get(f"{request.method} {path}", ok({}))
        if isinstance(answer, httpx2.TransportError):
            raise answer
        return answer


def ok(result: Any) -> httpx2.Response:
    return httpx2.Response(200, json={"result": result, "status": "ok", "time": 0.0})


def refused(status: int, reason: str) -> httpx2.Response:
    return httpx2.Response(status, json={"status": {"error": reason}, "time": 0.0})


def make_store(
    qdrant: Callable[[httpx2.Request], httpx2.Response], **bm25: Any
) -> QdrantChunkStore:
    http = httpx2.AsyncClient(
        base_url="http://qdrant.test:6333", transport=httpx2.MockTransport(qdrant)
    )
    return QdrantChunkStore(http, collection="chunks", bm25=bm25)


async def test_no_collection_has_no_identity() -> None:
    qdrant = FakeQdrant(
        {"GET /collections/chunks": refused(404, "Collection `chunks` doesn't exist!")}
    )

    assert await make_store(qdrant).identity() is None


async def test_a_collection_tells_the_model_it_was_made_for() -> None:
    metadata = {"embedding_model": "local", "dimensions": 2, "probe": [0.6, 0.8]}
    qdrant = FakeQdrant({"GET /collections/chunks": ok({"config": {"metadata": metadata}})})

    assert await make_store(qdrant).identity() == IDENTITY


async def test_a_collection_made_by_something_else_is_refused() -> None:
    qdrant = FakeQdrant({"GET /collections/chunks": ok({"config": {}})})

    with pytest.raises(ConflictError, match="wasn't made by this module"):
        await make_store(qdrant).identity()


async def test_the_collection_is_made_for_the_model_with_bm25_and_an_index_on_source() -> None:
    qdrant = FakeQdrant()

    await make_store(qdrant).create(IDENTITY)

    assert qdrant.calls == [
        (
            "PUT",
            "/collections/chunks",
            {
                "vectors": {"dense": {"size": 2, "distance": "Cosine"}},
                "sparse_vectors": {"bm25": {"modifier": "idf"}},
                "metadata": {"embedding_model": "local", "dimensions": 2, "probe": [0.6, 0.8]},
            },
        ),
        (
            "PUT",
            "/collections/chunks/index?wait=true",
            {"field_name": "source", "field_schema": "keyword"},
        ),
    ]


async def test_a_collection_made_meanwhile_is_left_as_it_is() -> None:
    qdrant = FakeQdrant(
        {"PUT /collections/chunks": refused(409, "Collection `chunks` already exists!")}
    )

    await make_store(qdrant).create(IDENTITY)

    assert [call[1] for call in qdrant.calls][-1] == "/collections/chunks/index?wait=true"


async def test_a_chunk_is_kept_under_an_id_made_from_the_app_s_with_its_text_for_bm25() -> None:
    qdrant = FakeQdrant()

    await make_store(qdrant).upsert([StoredChunk(RETURNS, [0.1, 0.2])])

    method, path, body = qdrant.calls[0]
    assert (method, path) == ("PUT", "/collections/chunks/points?wait=true")
    assert body == {
        "points": [
            {
                "id": point_id("returns-1"),
                "vector": {
                    "dense": [0.1, 0.2],
                    "bm25": {
                        "text": "Returns\nItems can be returned within 30 days.",
                        "model": "qdrant/bm25",
                    },
                },
                "payload": {
                    "id": "returns-1",
                    "source": "help/returns.md",
                    "text": "Items can be returned within 30 days.",
                    "title": "Returns",
                    "metadata": {"page": 1},
                },
            }
        ]
    }
    # The same app id, the same point: storing it again replaces it.
    assert point_id("returns-1") == point_id("returns-1") != point_id("returns-2")


async def test_bm25_s_options_go_with_every_text_when_set() -> None:
    qdrant = FakeQdrant()
    untitled = RETURNS.model_copy(update={"title": None})

    await make_store(qdrant, language="portuguese", avg_len=103).upsert(
        [StoredChunk(untitled, [0.1, 0.2])]
    )

    assert qdrant.calls[0][2]["points"][0]["vector"]["bm25"] == {
        "text": "Items can be returned within 30 days.",
        "model": "qdrant/bm25",
        "options": {"language": "portuguese", "avg_len": 103},
    }


async def test_a_source_s_chunks_are_counted_then_deleted() -> None:
    qdrant = FakeQdrant({"POST /collections/chunks/points/count": ok({"count": 3})})

    assert await make_store(qdrant).delete_source("help/returns.md") == 3

    where = {"must": [{"key": "source", "match": {"value": "help/returns.md"}}]}
    assert qdrant.calls == [
        ("POST", "/collections/chunks/points/count", {"filter": where, "exact": True}),
        ("POST", "/collections/chunks/points/delete?wait=true", {"filter": where}),
    ]


@pytest.mark.parametrize(
    "counted", [ok({"count": 0}), refused(404, "Collection `chunks` doesn't exist!")]
)
async def test_a_source_with_nothing_stored_deletes_nothing(counted: httpx2.Response) -> None:
    qdrant = FakeQdrant({"POST /collections/chunks/points/count": counted})

    assert await make_store(qdrant).delete_source("help/returns.md") == 0
    assert len(qdrant.calls) == 1


async def test_the_sources_are_listed_by_name_with_their_counts() -> None:
    # A source whose chunks were all deleted is still counted, at 0: it's left out.
    hits = [
        {"value": "y.md", "count": 1},
        {"value": "help/returns.md", "count": 2},
        {"value": "gone.md", "count": 0},
    ]
    qdrant = FakeQdrant({"POST /collections/chunks/facet": ok({"hits": hits})})

    assert await make_store(qdrant).sources() == [
        SourceSummary(source="help/returns.md", chunks=2),
        SourceSummary(source="y.md", chunks=1),
    ]
    assert qdrant.calls[0][2] == {"key": "source", "limit": 10_000, "exact": True}


async def test_no_collection_lists_no_sources() -> None:
    qdrant = FakeQdrant(
        {"POST /collections/chunks/facet": refused(404, "Collection `chunks` doesn't exist!")}
    )

    assert await make_store(qdrant).sources() == []


@pytest.mark.parametrize(
    ("answer", "kind", "message"),
    [
        (httpx2.ReadTimeout("slow"), ServiceTimeoutError, "Qdrant didn't answer in time."),
        (httpx2.ConnectError("refused"), ServiceUnavailableError, "Qdrant can't be reached."),
        (
            refused(400, "Wrong input: Vector dimension error: expected dim: 2, got 3"),
            ServiceError,
            "Qdrant refused the request with status 400: Wrong input: Vector dimension error: "
            "expected dim: 2, got 3",
        ),
        (
            httpx2.Response(500, text="oops"),
            ServiceError,
            "Qdrant refused the request with status 500.",
        ),
        (
            httpx2.Response(403, json={"status": "forbidden"}),
            ServiceError,
            "Qdrant refused the request with status 403.",
        ),
    ],
)
async def test_failures_become_rag_errors_with_qdrant_s_reason(
    answer: Answer, kind: type[ServiceError], message: str
) -> None:
    qdrant = FakeQdrant({"PUT /collections/chunks/points?wait=true": answer})

    with pytest.raises(kind) as raised:
        await make_store(qdrant).upsert([StoredChunk(RETURNS, [0.1, 0.2])])

    assert str(raised.value) == message


async def test_ready_when_qdrant_says_so_asked_with_a_short_timeout() -> None:
    requests: list[httpx2.Request] = []

    def qdrant(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, text="all shards are ready")

    assert await make_store(qdrant).is_ready() is True

    assert str(requests[0].url) == "http://qdrant.test:6333/readyz"
    assert requests[0].extensions["timeout"]["read"] == READINESS_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    "answer",
    [httpx2.Response(503, text="some shards are not ready"), httpx2.ConnectError("refused")],
)
async def test_not_ready_while_loading_or_unreachable(answer: Answer) -> None:
    qdrant = FakeQdrant({"GET /readyz": answer})

    assert await make_store(qdrant).is_ready() is False


async def test_closing_closes_the_http_client() -> None:
    http = httpx2.AsyncClient(base_url="http://qdrant.test:6333")

    await QdrantChunkStore(http, collection="chunks").aclose()

    assert http.is_closed


SEARCH = "POST /collections/chunks/points/query"
RETURNED = {"with_payload": True, "with_vector": ["dense"]}


def point(score: float) -> dict[str, Any]:
    return {
        "id": point_id("returns-1"),
        "score": score,
        "payload": RETURNS.model_dump(mode="json"),
        "vector": {"dense": [0.1, 0.2]},
    }


async def test_a_hybrid_search_fuses_both_halves_by_rank_within_the_sources_asked() -> None:
    qdrant = FakeQdrant({SEARCH: ok({"points": [point(0.83)]})})
    query = Query("How long?", [0.6, 0.8], 5, "hybrid", ("help/returns.md",))

    found = await make_store(qdrant, language="portuguese").search(query)

    assert found == [Found(RETURNS, 0.83, [0.1, 0.2])]
    where = {"filter": {"must": [{"key": "source", "match": {"any": ["help/returns.md"]}}]}}
    words = {"text": "How long?", "model": "qdrant/bm25", "options": {"language": "portuguese"}}
    assert qdrant.calls[0][2] == {
        "prefetch": [
            {"query": [0.6, 0.8], "using": "dense", "limit": 20, **where},
            {"query": words, "using": "bm25", "limit": 20, **where},
        ],
        "query": {"fusion": "rrf"},
        "limit": 5,
        **RETURNED,
    }


async def test_more_hits_asked_bring_more_candidates_to_fuse() -> None:
    qdrant = FakeQdrant({SEARCH: ok({"points": []})})

    await make_store(qdrant).search(Query("How long?", [0.6, 0.8], 10, "hybrid"))

    assert [half["limit"] for half in qdrant.calls[0][2]["prefetch"]] == [40, 40]


@pytest.mark.parametrize(
    ("mode", "half"),
    [
        ("dense", {"query": [0.6, 0.8], "using": "dense"}),
        ("words", {"query": {"text": "How long?", "model": "qdrant/bm25"}, "using": "bm25"}),
    ],
)
async def test_one_half_alone_searches_by_meaning_or_by_words(
    mode: Mode, half: dict[str, Any]
) -> None:
    qdrant = FakeQdrant({SEARCH: ok({"points": [point(0.7)]})})

    found = await make_store(qdrant).search(Query("How long?", [0.6, 0.8], 3, mode))

    assert found[0].score == 0.7
    assert qdrant.calls[0][2] == {**half, "limit": 3, **RETURNED}


async def test_no_collection_finds_nothing() -> None:
    qdrant = FakeQdrant({SEARCH: refused(404, "Collection `chunks` doesn't exist!")})

    assert await make_store(qdrant).search(Query("How long?", [0.6, 0.8], 5, "hybrid")) == []
