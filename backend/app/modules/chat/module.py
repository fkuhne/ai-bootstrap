"""The chat module, as the core plugs it in (docs/foundations.md#chat-whole-or-streamed).

It has no clients and no service of its own: it asks the core's LLM port, whose readiness the
core checks.
"""

from app.core.modules import Module
from app.modules.chat.config import ChatSettings
from app.modules.chat.router import router

MODULE = Module(name="chat", router=router, settings=ChatSettings)
