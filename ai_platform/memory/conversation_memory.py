from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from ai_platform.memory.repository import ConversationRepository

MAX_HISTORY_MESSAGES = 10
DEFAULT_TURN_SUMMARY_LIMIT = 2


@dataclass(frozen=True)
class HistoryMessage:
    """A (role, content) pair ready to hand to an LLM prompt.

    This is the seam a future milestone can use to swap recency-based
    retrieval for something smarter (embeddings, relevance ranking)
    without changing `PromptBuilder` or `ChatWorkflow`.
    """

    role: str
    content: str


@dataclass(frozen=True)
class TurnSummary:
    """A compact, mechanically-derived record of one prior turn's tool
    activity - what tool(s) ran, with what parameters, and which business
    entities (customer/vendor names and codes, invoice numbers) appeared
    in their results. Lets the planner resolve a follow-up like "which of
    those belong to ABC Industries?" without re-sending the full,
    potentially large, prior tool result.
    """

    tool_calls: list[dict[str, Any]]
    entities: dict[str, list[str]]


class ConversationMemory:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def get_context_window(self, conversation_id: uuid.UUID) -> list[HistoryMessage]:
        messages = await self._repository.get_messages(conversation_id)
        recent = messages[-MAX_HISTORY_MESSAGES:]
        return [HistoryMessage(role=m.role, content=m.content) for m in recent]

    async def get_recent_turn_summaries(
        self, conversation_id: uuid.UUID, limit: int = DEFAULT_TURN_SUMMARY_LIMIT
    ) -> list[TurnSummary]:
        summaries = await self._repository.list_recent_turn_summaries(conversation_id, limit)
        return [TurnSummary(tool_calls=s.tool_calls, entities=s.entities) for s in summaries]
