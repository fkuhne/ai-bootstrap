"""The RAG module's own error, which a caller tells apart; every other failure is one of the
core's (`app.core.errors`)."""

from app.core.errors import ConflictError


class RagModelChangedError(ConflictError):
    """The collection holds another embedding model's vectors."""
