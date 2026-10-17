"""The app's modules: capabilities it includes or leaves out (docs/foundations.md#modules).

Each lives in its own package here, and exposes one `Module`. To add one, add its line below;
to remove one, delete its line and its package, then regenerate the API's schema and types.
"""

from app.core.modules import Module
from app.modules import chat, conversations, decision, rag

MODULES: tuple[Module, ...] = (chat.MODULE, conversations.MODULE, decision.MODULE, rag.MODULE)
