"""The RAG module as the app runs it: its settings, its endpoints, its readiness, and its
clients' life."""

import json
from collections.abc import AsyncIterator, Sequence

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.core.config import forget_settings
from app.core.errors import (
    ServiceError,
    ServiceRateLimitedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from app.llm.dependencies import get_llm_client
from app.llm.fake_llm_client import FakeLLMClient
from app.main import create_app
from app.modules.rag import MODULE
from app.modules.rag.answers import REFUSAL
from app.modules.rag.chunk_store import StoredChunk
from app.modules.rag.chunks import Chunk, Hit, Mode, SourceSummary
from app.modules.rag.config import RagSettings
from app.modules.rag.dependencies import get_chunk_index
from app.modules.rag.exceptions import RagModelChangedError
from app.modules.rag.factory import create_chunk_store, create_embedder
from app.modules.rag.fake_chunk_store import FakeChunkStore
from app.modules.rag.fake_embedder import FakeEmbedder
from app.modules.rag.index import ChunkIndex
from app.modules.rag.openai_compatible_embedder import OpenAICompatibleEmbedder
from app.modules.rag.qdrant_chunk_store import QdrantChunkStore
from app.modules.rag.schemas import SearchRequest
from app.openapi import schema
from tests.helpers import USAGE, ScriptedLLM, events

pytestmark = pytest.mark.anyio


@pytest.fixture
def rag_app() -> FastAPI:
    app = create_app(modules=[MODULE])
    app.state.rag_embedder = FakeEmbedder()
    app.state.rag_chunk_store = FakeChunkStore()
    app.state.rag_index = ChunkIndex(
        app.state.rag_embedder, app.state.rag_chunk_store, model="fake", collection="chunks"
    )
    app.dependency_overrides[get_llm_client] = FakeLLMClient
    return app


@pytest.fixture
async def client(rag_app: FastAPI) -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=rag_app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def test_the_module_is_on_by_default_and_its_switch_turns_it_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = RagSettings()
    assert (settings.provider, str(settings.qdrant_url), str(settings.embedding_base_url)) == (
        "qdrant",
        "http://qdrant:6333/",
        "http://embedding:8080/v1",
    )
    assert MODULE.enabled() is True

    monkeypatch.setenv("RAG_ENABLED", "0")
    forget_settings()

    assert MODULE.enabled() is False


def test_the_provider_picks_the_implementation_and_no_longer_turns_it_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_PROVIDER", "off")

    with pytest.raises(ValidationError, match="'qdrant' or 'fake'"):
        RagSettings()


def test_a_format_must_say_where_the_text_goes(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match=r"must contain \{text\}"):
        RagSettings(query_format="query: ")

    # A model that wants nothing around the text.
    monkeypatch.setenv("RAG_DOCUMENT_FORMAT", "{text}")

    assert RagSettings().document_format == "{text}"


@pytest.mark.parametrize(
    ("embedder_ready", "store_ready", "status"),
    [(True, True, "ok"), (False, True, "unavailable"), (True, False, "unavailable")],
)
async def test_readiness_needs_both_the_embedding_model_and_the_store(
    rag_app: FastAPI,
    client: httpx2.AsyncClient,
    embedder_ready: bool,
    store_ready: bool,
    status: str,
) -> None:
    rag_app.state.rag_embedder = FakeEmbedder(ready=embedder_ready)
    rag_app.state.rag_chunk_store = FakeChunkStore(ready=store_ready)

    response = await client.get("/api/health/ready")

    assert response.json()["checks"]["rag"] == status


def test_off_the_app_leaves_it_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_ENABLED", "0")

    # Readiness checks the app's modules, and this one isn't among them.
    assert MODULE not in create_app().state.modules


@pytest.mark.parametrize(
    ("provider", "embedder_type", "store_type"),
    [
        ("fake", FakeEmbedder, FakeChunkStore),
        ("qdrant", OpenAICompatibleEmbedder, QdrantChunkStore),
    ],
)
async def test_the_lifespan_creates_the_clients_and_closes_them(
    monkeypatch: pytest.MonkeyPatch, provider: str, embedder_type: type, store_type: type
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("RAG_PROVIDER", provider)
    app = create_app()
    closed: list[str] = []

    async with app.router.lifespan_context(app):
        embedder, store = app.state.rag_embedder, app.state.rag_chunk_store
        assert (type(embedder), type(store)) == (embedder_type, store_type)
        assert isinstance(app.state.rag_index, ChunkIndex)
        # Only closing is checked here; the adapters' own tests cover the rest.
        monkeypatch.setattr(embedder, "aclose", lambda: _record(closed, "embedder"))
        monkeypatch.setattr(store, "aclose", lambda: _record(closed, "store"))

    assert closed == ["embedder", "store"]


async def _record(closed: list[str], name: str) -> None:
    closed.append(name)


async def test_the_factory_builds_the_embedder_from_the_settings() -> None:
    sent: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        data = [{"object": "embedding", "index": 0, "embedding": [1.0]}]
        return httpx2.Response(200, json={"object": "list", "model": "m", "data": data})

    settings = RagSettings(
        embedding_base_url="https://api.openai.com/v1",  # type: ignore[arg-type]
        embedding_api_key="k2",  # type: ignore[arg-type]
        embedding_model="text-embedding-3-small",
        query_format="{text}",
        timeout_seconds=12,
    )
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    embedder = create_embedder(settings, http_client=http)
    await embedder.embed_query("refund")
    await embedder.aclose()

    assert str(sent[0].url) == "https://api.openai.com/v1/embeddings"
    assert sent[0].headers["authorization"] == "Bearer k2"
    assert sent[0].extensions["timeout"]["read"] == 12
    assert json.loads(sent[0].content)["model"] == "text-embedding-3-small"
    assert json.loads(sent[0].content)["input"] == ["refund"]
    assert isinstance(create_embedder(RagSettings(provider="fake")), FakeEmbedder)


@pytest.mark.parametrize(("api_key", "header"), [(None, None), ("q1", "q1")])
async def test_the_factory_builds_the_store_from_the_settings(
    api_key: str | None, header: str | None
) -> None:
    sent: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, text="all shards are ready")

    settings = RagSettings(qdrant_url="https://qdrant.example:6333", qdrant_api_key=api_key)  # type: ignore[arg-type]

    store = create_chunk_store(settings, transport=httpx2.MockTransport(handler))
    assert await store.is_ready()
    await store.aclose()

    assert str(sent[0].url) == "https://qdrant.example:6333/readyz"
    assert sent[0].headers.get("api-key") == header
    assert isinstance(create_chunk_store(RagSettings(provider="fake")), FakeChunkStore)


async def test_the_factory_gives_the_store_its_collection_and_bm25_s_options() -> None:
    sent: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, json={"result": {}, "status": "ok"})

    settings = RagSettings(collection="docs", bm25_language="portuguese", bm25_avg_len=103)
    store = create_chunk_store(settings, transport=httpx2.MockTransport(handler))
    chunk = Chunk(id="a", source="s", text="Os reembolsos.")
    await store.upsert([StoredChunk(chunk, [1.0])])
    await store.aclose()

    assert sent[0].url.path == "/collections/docs/points"
    bm25 = json.loads(sent[0].content)["points"][0]["vector"]["bm25"]
    assert bm25["options"] == {"language": "portuguese", "avg_len": 103}


def test_by_default_a_chunk_s_title_has_its_place_and_bm25_has_qdrant_s_defaults() -> None:
    settings = RagSettings()

    assert settings.document_format == "title: {title} | text: {text}"
    assert (settings.collection, settings.bm25_language, settings.bm25_avg_len) == (
        "chunks",
        None,
        None,
    )
    with pytest.raises(ValidationError):
        RagSettings(collection="no/slashes")


CHUNKS = {
    "chunks": [
        {"id": "r1", "source": "help/returns.md", "title": "Returns", "text": "Within 30 days."},
        {"id": "r2", "source": "help/returns.md", "text": "Unused items only."},
        {"id": "s1", "source": "help/shipping.md", "text": "Three working days."},
    ]
}


async def test_chunks_are_stored_listed_and_a_source_s_deleted(
    client: httpx2.AsyncClient,
) -> None:
    stored = await client.put("/api/rag/chunks", json=CHUNKS)
    listed = await client.get("/api/rag/sources")
    # A source holding slashes stays one path parameter.
    deleted = await client.delete("/api/rag/sources/help/returns.md")
    left = await client.get("/api/rag/sources")

    assert stored.json() == {"stored": 3}
    assert listed.json() == {
        "sources": [
            {"source": "help/returns.md", "chunks": 2},
            {"source": "help/shipping.md", "chunks": 1},
        ]
    }
    assert deleted.json() == {"deleted": 2}
    assert left.json() == {"sources": [{"source": "help/shipping.md", "chunks": 1}]}


async def test_a_request_with_an_id_twice_is_refused(client: httpx2.AsyncClient) -> None:
    twice = {"chunks": [CHUNKS["chunks"][0], CHUNKS["chunks"][0]]}

    response = await client.put("/api/rag/chunks", json=twice)

    assert response.status_code == httpx2.codes.UNPROCESSABLE_CONTENT


class FailingIndex(ChunkIndex):
    def __init__(self, error: ServiceError) -> None:
        super().__init__(FakeEmbedder(), FakeChunkStore(), model="fake", collection="chunks")
        self.error = error

    async def store(self, chunks: object) -> int:
        raise self.error

    async def sources(self) -> list[SourceSummary]:
        raise self.error

    async def search(
        self,
        text: str,
        *,
        limit: int,
        mode: Mode = "hybrid",
        sources: Sequence[str] | None = None,
    ) -> list[Hit]:
        raise self.error


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (RagModelChangedError("another model"), httpx2.codes.CONFLICT),
        (ServiceTimeoutError("slow"), httpx2.codes.GATEWAY_TIMEOUT),
        (ServiceUnavailableError("down"), httpx2.codes.SERVICE_UNAVAILABLE),
        (ServiceRateLimitedError("busy"), httpx2.codes.TOO_MANY_REQUESTS),
        (ServiceError("refused"), httpx2.codes.BAD_GATEWAY),
    ],
)
async def test_errors_become_http_errors(
    rag_app: FastAPI, client: httpx2.AsyncClient, error: ServiceError, status_code: int
) -> None:
    rag_app.dependency_overrides[get_chunk_index] = lambda: FailingIndex(error)

    stored = await client.put("/api/rag/chunks", json=CHUNKS)
    listed = await client.get("/api/rag/sources")

    assert (stored.status_code, stored.json()) == (status_code, {"detail": str(error)})
    assert listed.status_code == status_code


ASK = {"messages": [{"role": "user", "content": "How long until returns are refunded?"}]}


async def stored(client: httpx2.AsyncClient) -> None:
    assert (await client.put("/api/rag/chunks", json=CHUNKS)).status_code == httpx2.codes.OK


async def test_a_search_answers_hits_with_their_scores_and_similarities(
    client: httpx2.AsyncClient,
) -> None:
    await stored(client)

    response = await client.post(
        "/api/rag/search", json={"query": "Within 30 days", "limit": 2, "mode": "words"}
    )

    hits = response.json()["hits"]
    # Both share a word, "days"; the one with more of the question's comes first.
    assert [hit["chunk"]["id"] for hit in hits] == ["r1", "s1"]
    assert hits[0]["score"] > hits[1]["score"]
    assert set(hits[0]) == {"chunk", "score", "similarity"}


async def test_an_answer_whole_holds_its_numbered_sources(
    rag_app: FastAPI, client: httpx2.AsyncClient
) -> None:
    rag_app.dependency_overrides[get_llm_client] = lambda: ScriptedLLM()
    await stored(client)

    answer = (await client.post("/api/rag/ask", json={**ASK, "limit": 2})).json()

    assert (answer["content"], answer["model"], answer["refused"]) == ("Hello", "scripted", False)
    assert [source["number"] for source in answer["sources"]] == [1, 2]


async def test_an_answer_streams_its_sources_first_then_the_model_s_answer(
    rag_app: FastAPI, client: httpx2.AsyncClient
) -> None:
    rag_app.dependency_overrides[get_llm_client] = lambda: ScriptedLLM()
    await stored(client)

    streamed = events((await client.post("/api/rag/ask/stream", json=ASK)).text)

    assert [name for name, _data in streamed] == ["sources", "reasoning", "token", "token", "done"]
    assert len(streamed[0][1]["sources"]) == 3
    assert streamed[-1][1] == {
        "model": "scripted",
        "finish_reason": "stop",
        "usage": USAGE,
        "refused": False,
    }


async def test_a_refused_question_streams_the_refusal_without_asking_the_model(
    rag_app: FastAPI, client: httpx2.AsyncClient
) -> None:
    llm = ScriptedLLM()
    rag_app.dependency_overrides[get_llm_client] = lambda: llm

    streamed = events((await client.post("/api/rag/ask/stream", json=ASK)).text)

    assert streamed == [
        ("sources", {"sources": []}),
        ("token", {"text": REFUSAL}),
        ("done", {"model": None, "finish_reason": None, "usage": None, "refused": True}),
    ]
    assert llm.sent == []


async def test_a_search_that_fails_before_streaming_answers_with_its_status(
    rag_app: FastAPI, client: httpx2.AsyncClient
) -> None:
    rag_app.dependency_overrides[get_chunk_index] = lambda: FailingIndex(
        ServiceUnavailableError("Qdrant can't be reached.")
    )

    response = await client.post("/api/rag/ask/stream", json=ASK)

    assert response.status_code == httpx2.codes.SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "Qdrant can't be reached."}


async def test_a_model_that_fails_mid_answer_ends_the_stream_with_an_error_event(
    rag_app: FastAPI, client: httpx2.AsyncClient
) -> None:
    llm = ScriptedLLM(ServiceUnavailableError("The LLM endpoint can't be reached."), pieces_first=1)
    rag_app.dependency_overrides[get_llm_client] = lambda: llm
    await stored(client)

    streamed = events((await client.post("/api/rag/ask/stream", json=ASK)).text)

    assert streamed[-1] == (
        "error",
        {
            "status": httpx2.codes.SERVICE_UNAVAILABLE,
            "detail": "The LLM endpoint can't be reached.",
        },
    )


def test_the_published_search_example_is_a_valid_request() -> None:
    for example in schema()["components"]["schemas"]["SearchRequest"]["examples"]:
        SearchRequest.model_validate(example)
