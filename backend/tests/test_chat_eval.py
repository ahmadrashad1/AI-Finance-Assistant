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
from domains.finance.tools.get_customer_balance import GET_CUSTOMER_BALANCE_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL
from domains.finance.tools.get_vendor_balance import GET_VENDOR_BALANCE_TOOL
from domains.finance.tools.search_invoices import SEARCH_INVOICES_TOOL
from tests.fakes import FakeLLMService


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    registry.register(SEARCH_INVOICES_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    registry.register(GET_CUSTOMER_BALANCE_TOOL)
    registry.register(GET_VENDOR_BALANCE_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phrasing",
    [
        "Show unpaid invoices",
        "Which invoices haven't been paid?",
        "Outstanding invoices?",
        "Who still owes us money?",
        "Customers with overdue invoices",
    ],
)
async def test_eval_unpaid_invoice_phrasings_all_select_get_unpaid_invoices(
    clean_db: None, db_session: AsyncSession, phrasing: str
) -> None:
    """Milestone 5 acceptance: every natural-language phrasing for 'who
    owes us money' must plan get_unpaid_invoices - proves intent routing
    lives in the LLM/prompt layer, not in keyword-matching code."""
    llm_service = FakeLLMService(
        tokens=["Here are the unpaid invoices."],
        plan_response='{"tool_calls": [{"tool": "get_unpaid_invoices", "parameters": {}}]}',
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id=f"eval-unpaid-{phrasing}", message=phrasing)
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_unpaid_invoices"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phrasing",
    [
        "Find invoice INV-1045",
        "Show invoice INV-1045",
        "Look up invoice INV-1045",
    ],
)
async def test_eval_search_invoices_phrasings_all_select_search_invoices(
    clean_db: None, db_session: AsyncSession, phrasing: str
) -> None:
    """Milestone 6: single-invoice lookup phrasings must plan
    search_invoices, not a nonexistent get_invoice tool."""
    llm_service = FakeLLMService(
        tokens=["Here's that invoice."],
        plan_response=(
            '{"tool_calls": [{"tool": "search_invoices", '
            '"parameters": {"invoice_number": "INV-1045"}}]}'
        ),
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id=f"eval-search-{phrasing}", message=phrasing)
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["search_invoices"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phrasing",
    [
        "Show invoices overdue by 30 days",
        "Which invoices are past due?",
        "Show Northwind's overdue invoices",
    ],
)
async def test_eval_overdue_phrasings_all_select_get_overdue_invoices(
    clean_db: None, db_session: AsyncSession, phrasing: str
) -> None:
    """Milestone 6: day-threshold / explicitly-overdue phrasings must plan
    get_overdue_invoices, not the broader get_unpaid_invoices."""
    llm_service = FakeLLMService(
        tokens=["Here are the overdue invoices."],
        plan_response='{"tool_calls": [{"tool": "get_overdue_invoices", "parameters": {}}]}',
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id=f"eval-overdue-{phrasing}", message=phrasing)
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_overdue_invoices"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phrasing",
    [
        "How much does Northwind Manufacturing owe us?",
        "What's Acme Corp's balance?",
        "How much do we have outstanding from Globex Inc?",
    ],
)
async def test_eval_customer_balance_phrasings_all_select_get_customer_balance(
    clean_db: None, db_session: AsyncSession, phrasing: str
) -> None:
    """Milestone 6: single-customer balance phrasings must plan
    get_customer_balance."""
    llm_service = FakeLLMService(
        tokens=["Here's their balance."],
        plan_response=(
            '{"tool_calls": [{"tool": "get_customer_balance", '
            '"parameters": {"customer_name": "placeholder"}}]}'
        ),
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id=f"eval-cb-{phrasing}", message=phrasing)
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_customer_balance"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phrasing",
    [
        "What do we owe Summit Traders?",
        "What's our balance with Cascade Logistics?",
        "How much do we owe Apex Supplies?",
    ],
)
async def test_eval_vendor_balance_phrasings_all_select_get_vendor_balance(
    clean_db: None, db_session: AsyncSession, phrasing: str
) -> None:
    """Milestone 6: single-vendor balance phrasings must plan
    get_vendor_balance."""
    llm_service = FakeLLMService(
        tokens=["Here's the vendor balance."],
        plan_response=(
            '{"tool_calls": [{"tool": "get_vendor_balance", '
            '"parameters": {"vendor_name": "placeholder"}}]}'
        ),
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id=f"eval-vb-{phrasing}", message=phrasing)
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_vendor_balance"]
