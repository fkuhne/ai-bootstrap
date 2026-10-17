"""FastAPI dependencies of the conversations domain."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request

from app.llm.dependencies import LLMClientDep
from app.modules.conversations.conversation_answerer import ConversationAnswerer
from app.modules.conversations.conversation_store import ConversationStore, ConversationWithMessages
from app.users.dependencies import CurrentUserDep


async def get_conversation_store(request: Request) -> ConversationStore:
    """The store the lifespan created for this application. Tests override this."""
    return cast(ConversationStore, request.app.state.conversation_store)


ConversationStoreDep = Annotated[ConversationStore, Depends(get_conversation_store)]


async def get_conversation_answerer(
    store: ConversationStoreDep, llm: LLMClientDep
) -> ConversationAnswerer:
    """An answerer on this request's store and model, so tests' doubles reach it."""
    return ConversationAnswerer(store, llm)


ConversationAnswererDep = Annotated[ConversationAnswerer, Depends(get_conversation_answerer)]


async def get_owned_conversation(
    conversation_id: UUID, user_id: CurrentUserDep, store: ConversationStoreDep
) -> ConversationWithMessages:
    """The conversation in the path, read with its messages, if it's this user's; otherwise
    `ConversationNotFoundError`, answered 404. As a dependency it runs before the endpoint, so
    a streamed endpoint answers 404 too, instead of an empty stream."""
    return await store.get_conversation(user_id, conversation_id)


OwnedConversationDep = Annotated[ConversationWithMessages, Depends(get_owned_conversation)]
