from __future__ import annotations

import uuid
from dataclasses import dataclass

from ai_platform.memory.repository import ConversationRepository

MAX_HISTORY_MESSAGES = 10


@dataclass(frozen=True)
class HistoryMessage:
    """A (role, content) pair ready to hand to an LLM prompt.

    This is the seam a future milestone can use to swap recency-based
    retrieval for something smarter (embeddings, relevance ranking)
    without changing `PromptBuilder` or `ChatWorkflow`.
    """

    role: str
    content: str


class ConversationMemory:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def get_context_window(self, conversation_id: uuid.UUID) -> list[HistoryMessage]:
        messages = await self._repository.get_messages(conversation_id)
        recent = messages[-MAX_HISTORY_MESSAGES:]
        return [HistoryMessage(role=m.role, content=m.content) for m in recent]
