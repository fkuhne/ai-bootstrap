"""Adapter from the embedder port to any OpenAI-compatible embeddings API: llama.cpp's
server, or a provider's (Adapter)."""

import re
from collections.abc import Sequence

import openai
from openai import AsyncOpenAI

from app.core.errors import ServiceError
from app.core.services import READINESS_TIMEOUT_SECONDS
from app.llm.openai_errors import translate
from app.modules.rag.embedder import Document, Embedder, Vector

# How the endpoint is named in errors.
SERVICE = "The embedding endpoint"

# The places a format holds: `{text}`, and in a chunk's, `{title}`.
PLACES = re.compile(r"\{(text|title)\}")


class OpenAICompatibleEmbedder(Embedder):
    """POSTs the texts to `/embeddings`, each written in its format first. The SDK client
    carries the base URL, the key and the timeout."""

    def __init__(
        self, client: AsyncOpenAI, *, model: str, query_format: str, document_format: str
    ) -> None:
        self._client = client
        self._model = model
        self._query_format = query_format
        self._document_format = document_format

    async def embed_documents(self, documents: Sequence[Document]) -> list[Vector]:
        if not documents:
            return []
        return await self._embed(
            [_written(self._document_format, d.text, d.title) for d in documents]
        )

    async def embed_query(self, text: str) -> Vector:
        (vector,) = await self._embed([_written(self._query_format, text)])
        return vector

    async def is_ready(self) -> bool:
        """Embed one word, tried once with a short timeout. A server can answer before its
        model is loaded, so only an embedding shows it's ready."""
        try:
            await self._embed(["ping"], probing=True)
        except ServiceError:
            return False
        return True

    async def aclose(self) -> None:
        await self._client.close()

    async def _embed(self, texts: list[str], *, probing: bool = False) -> list[Vector]:
        try:
            if probing:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                    encoding_format="float",
                    timeout=READINESS_TIMEOUT_SECONDS,
                )
            else:
                response = await self._client.embeddings.create(
                    model=self._model, input=texts, encoding_format="float"
                )
        except openai.APIError as error:
            raise translate(error, SERVICE) from error
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if len(vectors) != len(texts):
            raise ServiceError(f"{SERVICE} answered {len(vectors)} vectors for {len(texts)} texts.")
        return vectors


def _written(text_format: str, text: str, title: str | None = None) -> str:
    """The text, and its title or "none", in their places in the format, in one pass, so
    neither is read for places itself. Not `str.format`: a format may hold other braces."""
    values = {"text": text, "title": title or "none"}
    return PLACES.sub(lambda place: values[place.group(1)], text_format)
