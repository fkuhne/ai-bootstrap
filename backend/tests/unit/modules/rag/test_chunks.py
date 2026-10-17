"""The chunk, as an app sends it: what's required, and what a request may hold."""

import pytest
from pydantic import ValidationError

from app.modules.rag.chunks import Chunk
from app.modules.rag.schemas import MAX_CHUNKS, StoreRequest
from app.openapi import schema


def test_a_chunk_needs_an_id_a_source_and_a_text() -> None:
    chunk = Chunk.model_validate({"id": "a", "source": "s", "text": "t"})

    assert (chunk.title, chunk.metadata) == (None, {})
    for missing in ("id", "source", "text"):
        with pytest.raises(ValidationError):
            Chunk.model_validate({"id": "a", "source": "s", "text": "t", missing: ""})


def test_a_request_holds_from_one_chunk_to_the_most_and_no_id_twice() -> None:
    one = {"id": "a", "source": "s", "text": "t"}

    with pytest.raises(ValidationError):
        StoreRequest.model_validate({"chunks": []})
    with pytest.raises(ValidationError):
        StoreRequest.model_validate(
            {"chunks": [{**one, "id": str(n)} for n in range(MAX_CHUNKS + 1)]}
        )
    with pytest.raises(ValidationError, match="each chunk's id must be unique"):
        StoreRequest.model_validate({"chunks": [one, {**one, "text": "other"}]})


def test_the_published_example_is_a_valid_request() -> None:
    for example in schema()["components"]["schemas"]["StoreRequest"]["examples"]:
        StoreRequest.model_validate(example)
