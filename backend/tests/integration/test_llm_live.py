"""Live checks against the configured LLM. Excluded by default; run them with:

    docker compose up -d --wait
    docker compose run --rm backend-checks pytest -m integration --no-cov

`LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` point them at another server, such as a cloud
provider.
"""

import pytest

from app.llm.config import LLMSettings
from app.llm.factory import create_llm_client
from app.llm.llm_client import ChatMessage, ContentDelta, ReasoningDelta, StreamEnd

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

QUESTION = [ChatMessage(role="user", content="Reply with exactly one word: pong")]
# Room for a model that reasons first. It may still spend all of it reasoning, so either
# reasoning or an answer shows the model produced something: this tests the integration,
# not the model.
PARAMETERS = {"max_tokens": 512}


async def test_the_configured_model_answers_whole_and_streamed() -> None:
    client = create_llm_client(LLMSettings())
    try:
        assert await client.is_ready()

        completion = await client.complete(QUESTION, parameters=PARAMETERS)
        parts = [part async for part in client.stream(QUESTION, parameters=PARAMETERS)]

        assert (completion.content or completion.reasoning or "").strip()
        assert completion.usage is not None
        streamed = "".join(p.text for p in parts if isinstance(p, ContentDelta | ReasoningDelta))
        assert streamed.strip()
        assert isinstance(parts[-1], StreamEnd)
        assert parts[-1].usage is not None
    finally:
        await client.aclose()
