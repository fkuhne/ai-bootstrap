"""Conversations: each user's conversations and their messages, stored in PostgreSQL, with the
database and its migrations (docs/foundations.md#conversations)."""

from app.modules.conversations.module import MODULE

__all__ = ["MODULE"]
