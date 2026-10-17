"""The adapter talks to a mock transport: real SDK, real HTTP parsing, no network."""

import json
from collections.abc import Callable
from typing import Any

import httpx2
import openai
import pytest
from openai import AsyncOpenAI

from app.core.errors import (
    ServiceError,
    ServiceRateLimitedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from app.core.services import READINESS_TIMEOUT_SECONDS
from app.llm.openai_errors import translate
from app.modules.rag.embedder import Document
from app.modules.rag.openai_compatible_embedder import SERVICE, OpenAICompatibleEmbedder

pytestmark = pytest.mark.anyio

Handler = Callable[[httpx2.Request], httpx2.Response]

# llama.cpp's answer to a text longer than its batch, as its server gave it.
TOO_LONG = {
    "error": {
        "code": 500,
        "message": "input (1203 tokens) is too large to process. increase the physical batch "
        "size (current batch size: 1024)",
        "type": "server_error",
    }
}


class EmbeddingServer:
    """A mock-transport handler that answers as an embeddings endpoint does, each vector made
    of its index and its text's length, listed in reverse as a server may; and keeps every
    request."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        texts = json.loads(request.content)["input"]
        data = [
            {"object": "embedding", "index": index, "embedding": [float(index), float(len(text))]}
            for index, text in enumerate(texts)
        ]
        usage = {"prompt_tokens": 1, "total_tokens": 1}
        return httpx2.Response(
            200, json={"object": "list", "model": "served", "data": data[::-1], "usage": usage}
        )

    def body(self) -> Any:
        return json.loads(self.requests[-1].content)


def make_embedder(
    handler: Handler,
    *,
    query_format: str = "query: {text}",
    document_format: str = "{text} (document)",
) -> OpenAICompatibleEmbedder:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    sdk = AsyncOpenAI(
        base_url="http://embedding.test/v1", api_key="test", max_retries=0, http_client=http
    )
    return OpenAICompatibleEmbedder(
        sdk, model="test-model", query_format=query_format, document_format=document_format
    )


async def test_chunks_are_written_in_their_format_and_come_back_in_order() -> None:
    server = EmbeddingServer()

    vectors = await make_embedder(server).embed_documents(
        [Document("first"), Document("the second")]
    )

    assert vectors == [[0.0, len("first (document)")], [1.0, len("the second (document)")]]
    assert str(server.requests[0].url) == "http://embedding.test/v1/embeddings"
    assert server.body() == {
        "model": "test-model",
        "input": ["first (document)", "the second (document)"],
        "encoding_format": "float",
    }


async def test_a_question_is_written_in_its_own_format() -> None:
    server = EmbeddingServer()

    vector = await make_embedder(server).embed_query("refund?")

    assert vector == [0.0, len("query: refund?")]
    assert server.body()["input"] == ["query: refund?"]


async def test_a_chunk_s_title_takes_its_place_in_the_format_or_reads_none() -> None:
    server = EmbeddingServer()
    embedder = make_embedder(server, document_format="title: {title} | text: {text}")

    await embedder.embed_documents(
        [Document("Within 30 days.", "Returns"), Document("No title here.")]
    )

    assert server.body()["input"] == [
        "title: Returns | text: Within 30 days.",
        "title: none | text: No title here.",
    ]


async def test_a_text_holding_a_place_s_name_is_kept_as_it_is() -> None:
    server = EmbeddingServer()
    embedder = make_embedder(server, document_format="title: {title} | text: {text}")

    await embedder.embed_documents([Document("Write {title} here.", "{text}")])

    assert server.body()["input"] == ["title: {text} | text: Write {title} here."]


async def test_a_format_keeps_its_other_braces() -> None:
    server = EmbeddingServer()

    await make_embedder(server, query_format='{"question": "{text}"}').embed_query("why")

    assert server.body()["input"] == ['{"question": "why"}']


async def test_no_chunks_make_no_request() -> None:
    server = EmbeddingServer()

    assert await make_embedder(server).embed_documents([]) == []
    assert server.requests == []


def failing(outcome: httpx2.Response | httpx2.TransportError) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if isinstance(outcome, httpx2.TransportError):
            raise outcome
        return outcome

    return handler


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (
            httpx2.Response(500, json=TOO_LONG),
            "The embedding endpoint refused the request with status 500: input (1203 tokens) is "
            "too large to process. increase the physical batch size (current batch size: 1024)",
        ),
        (
            httpx2.Response(401, json={"error": {"message": "Invalid API key"}}),
            "The embedding endpoint refused the request with status 401: Invalid API key",
        ),
        (
            httpx2.Response(404, text="Not Found"),
            "The embedding endpoint refused the request with status 404.",
        ),
        (httpx2.ConnectError("refused"), "The embedding endpoint can't be reached."),
        (httpx2.ReadTimeout("slow"), "The embedding endpoint didn't answer in time."),
    ],
)
async def test_failures_become_rag_errors_with_the_provider_s_reason(
    outcome: httpx2.Response | httpx2.TransportError, message: str
) -> None:
    with pytest.raises(ServiceError) as raised:
        await make_embedder(failing(outcome)).embed_documents([Document("a chunk")])

    assert str(raised.value) == message


async def test_a_wrong_number_of_vectors_is_an_error() -> None:
    def one_vector(request: httpx2.Request) -> httpx2.Response:
        data = [{"object": "embedding", "index": 0, "embedding": [1.0]}]
        return httpx2.Response(200, json={"object": "list", "model": "m", "data": data})

    with pytest.raises(ServiceError, match="1 vectors for 2 texts"):
        await make_embedder(one_vector).embed_documents([Document("one"), Document("two")])


def test_unexpected_sdk_errors_become_rag_errors() -> None:
    odd = openai.APIError("odd", httpx2.Request("POST", "http://embedding.test/v1"), body=None)

    assert str(translate(odd, SERVICE)) == "The embedding endpoint failed."


async def test_readiness_embeds_one_word_with_a_short_timeout() -> None:
    server = EmbeddingServer()

    assert await make_embedder(server).is_ready() is True

    assert len(server.requests) == 1
    assert server.requests[0].extensions["timeout"]["read"] == READINESS_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    "outcome",
    [
        httpx2.Response(503, json={"error": {"message": "Loading model"}}),
        httpx2.ConnectError("refused"),
    ],
)
async def test_a_failure_is_not_ready(outcome: httpx2.Response | httpx2.TransportError) -> None:
    assert await make_embedder(failing(outcome)).is_ready() is False


async def test_closing_closes_the_http_client() -> None:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(EmbeddingServer()))
    sdk = AsyncOpenAI(base_url="http://embedding.test/v1", api_key="test", http_client=http)
    embedder = OpenAICompatibleEmbedder(
        sdk, model="m", query_format="{text}", document_format="{text}"
    )

    await embedder.aclose()

    assert http.is_closed


@pytest.mark.parametrize(
    ("outcome", "kind"),
    [
        (httpx2.ReadTimeout("slow"), ServiceTimeoutError),
        (httpx2.ConnectError("refused"), ServiceUnavailableError),
        (httpx2.Response(429, json={"error": {"message": "Slow down"}}), ServiceRateLimitedError),
        # llama.cpp's answer while it loads its model: down for now, not refusing.
        (
            httpx2.Response(503, json={"error": {"message": "Loading model"}}),
            ServiceUnavailableError,
        ),
    ],
)
async def test_each_kind_of_failure_has_its_own_error(
    outcome: httpx2.Response | httpx2.TransportError, kind: type[ServiceError]
) -> None:
    with pytest.raises(kind):
        await make_embedder(failing(outcome)).embed_query("a question")
