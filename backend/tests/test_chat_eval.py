"""Minimal AI evaluation cases for Milestone 2/3's chat behavior.

These are not a substitute for the full Evaluation-Driven Development
framework (Milestone 8) - they exist to satisfy CLAUDE.md's "every feature
ships with ... AI evaluation cases" for this milestone's scope, using
FakeLLMService so they run deterministically in CI without a live model.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from tests.fakes import FakeLLMService


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository)
    prompt_builder = PromptBuilder()
    return ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=Planner(llm_service, registry, prompt_builder),
        tool_executor=tool_executor,
        request_id="eval-req",
    )


@pytest.mark.asyncio
async def test_eval_greeting_produces_non_empty_reply(
    clean_db: None, db_session: AsyncSession
) -> None:
    """A friendly greeting must produce a non-empty assistant reply."""
    llm_service = FakeLLMService(tokens=["Hello", "! How can I help?"])
    workflow = _make_workflow(db_session, llm_service)

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
    workflow = _make_workflow(db_session, llm_service)

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
    workflow = _make_workflow(db_session, llm_service)

    with pytest.raises(ValidationError):
        async for _ in workflow.run(ChatRequest(session_id="eval-session-3", message="")):
            pass

    assert llm_service.last_message is None


@pytest.mark.asyncio
async def test_eval_asking_for_the_date_selects_get_current_date_tool(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Asking what today's date is must select the get_current_date tool,
    not answer from context - this is the one thing Milestone 3 exists to
    prove."""
    llm_service = FakeLLMService(
        tokens=["It's July 7th, 2026."],
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id="eval-session-4", message="What's today's date?")
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_current_date"]


@pytest.mark.asyncio
async def test_eval_greeting_takes_direct_answer_branch(
    clean_db: None, db_session: AsyncSession
) -> None:
    """A greeting needs no tool - the planner must choose direct_answer,
    never touching the tool registry."""
    llm_service = FakeLLMService(tokens=["Hi there!"], plan_response='{"direct_answer": true}')
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e async for e in workflow.run(ChatRequest(session_id="eval-session-5", message="hi"))
    ]
    await db_session.commit()

    assert [e for e in events if e.type == "tool_call"] == []
    reply = "".join(e.content or "" for e in events if e.type == "token")
    assert reply.strip() != ""


@pytest.mark.asyncio
async def test_eval_ambiguous_request_can_short_circuit_with_clarification(
    clean_db: None, db_session: AsyncSession
) -> None:
    """An ambiguous request must be able to stop at a clarifying question
    before any tool executes."""
    llm_service = FakeLLMService(
        tokens=["should not be used"],
        plan_response='{"clarification_needed": "Which invoices do you mean?"}',
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id="eval-session-6", message="Show invoices")
        )
    ]
    await db_session.commit()

    assert [e.type for e in events] == ["token", "done"]
    assert events[0].content == "Which invoices do you mean?"
    assert uuid.UUID(events[1].conversation_id or "")
