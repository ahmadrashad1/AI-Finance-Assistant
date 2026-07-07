"""Minimal AI evaluation cases for Milestone 2's chat behavior.

These are not a substitute for the full Evaluation-Driven Development
framework (Milestone 8) - they exist to satisfy CLAUDE.md's "every feature
ships with ... AI evaluation cases" for this milestone's scope, using
FakeLLMService so they run deterministically in CI without a live model.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.prompt_builder import PromptBuilder
from tests.fakes import FakeLLMService


@pytest.mark.asyncio
async def test_eval_greeting_produces_non_empty_reply(
    clean_db: None, db_session: AsyncSession
) -> None:
    """A friendly greeting must produce a non-empty assistant reply."""
    llm_service = FakeLLMService(tokens=["Hello", "! How can I help?"])
    repository = ConversationRepository(db_session)
    workflow = ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id="eval-1",
    )

    events: list[ChatEvent] = [
        e async for e in workflow.run(ChatRequest(session_id="eval-session-1", message="Hello"))
    ]
    await db_session.commit()

    reply = "".join(e.content or "" for e in events if e.type == "token")
    assert reply.strip() != ""


@pytest.mark.asyncio
async def test_eval_conversation_history_reaches_the_prompt(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Prior turns must be visible to the LLM service on the next turn -
    verifies the memory wiring, not just that a reply comes back."""
    llm_service = FakeLLMService(tokens=["ok"])
    repository = ConversationRepository(db_session)
    workflow = ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id="eval-2",
    )

    conversation_id: str | None = None
    async for event in workflow.run(
        ChatRequest(session_id="eval-session-2", message="My favorite color is blue.")
    ):
        if event.type == "done":
            conversation_id = event.conversation_id
    await db_session.commit()
    assert conversation_id is not None

    async for _ in workflow.run(
        ChatRequest(
            session_id="eval-session-2",
            message="What's my favorite color?",
            conversation_id=conversation_id,
        )
    ):
        pass
    await db_session.commit()

    assert llm_service.last_history is not None
    assert any("blue" in m["content"].lower() for m in llm_service.last_history)


@pytest.mark.asyncio
async def test_eval_empty_message_never_reaches_the_llm(
    clean_db: None, db_session: AsyncSession
) -> None:
    """An empty message must be rejected before any model call - prevents
    wasted API spend and matches the 'no unsupported assumptions' AI
    responsibility from Ch.8."""
    from app.core.errors import ValidationError

    llm_service = FakeLLMService(tokens=["should never appear"])
    repository = ConversationRepository(db_session)
    workflow = ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id="eval-3",
    )

    with pytest.raises(ValidationError):
        async for _ in workflow.run(ChatRequest(session_id="eval-session-3", message="")):
            pass

    assert llm_service.last_message is None
