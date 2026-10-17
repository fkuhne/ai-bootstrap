"""Settings of the RAG module, read from `RAG_*` environment variables."""

from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import SettingsConfigDict

from app.core.config import ModuleSettings

Provider = Literal["qdrant", "fake"]

# Where the text goes in a format; a chunk's format may also hold `{title}`.
TEXT = "{text}"


class RagSettings(ModuleSettings):
    """How to reach Qdrant and the embedding model, or the fakes of both. The switch,
    `RAG_ENABLED`, also turns the local `qdrant` and `embedding` services off."""

    model_config = SettingsConfigDict(env_prefix="RAG_")

    provider: Provider = "qdrant"
    # Qdrant's REST API: the local service, or a Qdrant elsewhere with its key.
    qdrant_url: HttpUrl = HttpUrl("http://qdrant:6333")
    qdrant_api_key: SecretStr | None = None
    # Any OpenAI-compatible API with /embeddings: the local llama.cpp server, or a provider's.
    embedding_base_url: HttpUrl = HttpUrl("http://embedding:8080/v1")
    # llama.cpp's server needs no key.
    embedding_api_key: SecretStr = SecretStr("local")
    # llama.cpp's server answers with the model it loaded, whatever the name.
    embedding_model: str = "local"
    # How a question and a chunk are written before they're embedded, `{text}` standing for
    # the text, and in a chunk's `{title}`: some models want a task or a title around it. These
    # are EmbeddingGemma 2's; a model that wants nothing around the text takes `{text}`.
    query_format: str = "task: search result | query: {text}"
    document_format: str = "title: {title} | text: {text}"
    timeout_seconds: float = Field(default=60, gt=0)
    # The Qdrant collection the chunks are kept in, created on the first store.
    collection: str = Field(default="chunks", min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    # BM25's language, for its stop words and stems, such as english or portuguese, and the
    # chunks' average length in words. Unset, Qdrant's own defaults apply.
    bm25_language: str | None = None
    bm25_avg_len: float | None = Field(default=None, gt=0)
    # The similarity, from -1 to 1, below which a question's best chunk is too far from it to
    # answer from: the answer says the documents don't say. Unset, every question is answered.
    min_similarity: float | None = Field(default=None, ge=-1, le=1)

    @field_validator("query_format", "document_format")
    @classmethod
    def _holds_the_text(cls, value: str) -> str:
        if TEXT not in value:
            raise ValueError(f"must contain {TEXT}, where the text goes")
        return value
