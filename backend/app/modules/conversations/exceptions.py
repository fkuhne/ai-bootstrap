"""The conversations module's own error, which a caller tells apart; every other failure is one
of the core's (`app.core.errors`)."""

from uuid import UUID

from app.core.errors import NotFoundError


class ConversationNotFoundError(NotFoundError):
    """No conversation with this id belongs to the user: it doesn't exist, was deleted, or is
    someone else's. The three look the same, so ids can't be probed."""

    def __init__(self, conversation_id: UUID) -> None:
        super().__init__(f"No conversation {conversation_id}.")
        self.conversation_id = conversation_id
