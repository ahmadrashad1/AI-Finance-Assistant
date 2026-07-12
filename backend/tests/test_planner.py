from __future__ import annotations

import pytest

from ai_platform.memory.conversation_memory import HistoryMessage, TurnSummary
from ai_platform.orchestration.planner import Plan, Planner, ToolCall
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from app.core.errors import AIError
from tests.fakes import FakeLLMService


def test_plan_requires_exactly_one_branch_clarification_only() -> None:
    plan = Plan(clarification_needed="Which invoices?")
    assert plan.clarification_needed == "Which invoices?"


def test_plan_requires_exactly_one_branch_tool_calls_only() -> None:
    plan = Plan(tool_calls=[ToolCall(tool="get_current_date")])
    assert plan.tool_calls is not None
    assert plan.tool_calls[0].tool == "get_current_date"


def test_plan_requires_exactly_one_branch_direct_answer_only() -> None:
    plan = Plan(direct_answer=True)
    assert plan.direct_answer is True


def test_plan_rejects_zero_branches_set() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Plan()


def test_plan_rejects_multiple_branches_set() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Plan(direct_answer=True, clarification_needed="huh?")


@pytest.mark.asyncio
async def test_create_plan_parses_tool_calls_response() -> None:
    llm_service = FakeLLMService(
        tokens=[], plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}'
    )
    planner = Planner(llm_service, ToolRegistry(), PromptBuilder())

    plan = await planner.create_plan([], "What's today's date?")

    assert plan.tool_calls == [ToolCall(tool="get_current_date", parameters={})]


@pytest.mark.asyncio
async def test_create_plan_strips_markdown_code_fences() -> None:
    llm_service = FakeLLMService(tokens=[], plan_response='```json\n{"direct_answer": true}\n```')
    planner = Planner(llm_service, ToolRegistry(), PromptBuilder())

    plan = await planner.create_plan([], "hi")

    assert plan.direct_answer is True


@pytest.mark.asyncio
async def test_create_plan_raises_ai_error_on_malformed_json() -> None:
    llm_service = FakeLLMService(tokens=[], plan_response="not json at all")
    planner = Planner(llm_service, ToolRegistry(), PromptBuilder())

    with pytest.raises(AIError):
        await planner.create_plan([], "hi")


@pytest.mark.asyncio
async def test_create_plan_passes_history_and_tool_specs_to_the_llm() -> None:
    llm_service = FakeLLMService(tokens=[], plan_response='{"direct_answer": true}')
    registry = ToolRegistry()
    planner = Planner(llm_service, registry, PromptBuilder())
    history = [HistoryMessage(role="user", content="hello")]

    await planner.create_plan(history, "how are you?")

    assert llm_service.last_complete_history == [{"role": "user", "content": "hello"}]
    assert llm_service.last_complete_message == "how are you?"
    assert "direct_answer" in (llm_service.last_complete_system or "")


@pytest.mark.asyncio
async def test_create_plan_returns_clarification_when_tool_calls_exceed_the_cap() -> None:
    tool_calls_json = ", ".join(
        '{"tool": "get_current_date", "parameters": {}}' for _ in range(6)
    )
    llm_service = FakeLLMService(
        tokens=["unused"], plan_response=f'{{"tool_calls": [{tool_calls_json}]}}'
    )
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    planner = Planner(llm_service, registry, PromptBuilder())

    plan = await planner.create_plan([], "do six things")

    assert plan.clarification_needed is not None
    assert plan.tool_calls is None
    assert "narrow" in plan.clarification_needed.lower()


@pytest.mark.asyncio
async def test_create_plan_accepts_exactly_five_tool_calls() -> None:
    tool_calls_json = ", ".join(
        '{"tool": "get_current_date", "parameters": {}}' for _ in range(5)
    )
    llm_service = FakeLLMService(
        tokens=["unused"], plan_response=f'{{"tool_calls": [{tool_calls_json}]}}'
    )
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    planner = Planner(llm_service, registry, PromptBuilder())

    plan = await planner.create_plan([], "do five things")

    assert plan.tool_calls is not None
    assert len(plan.tool_calls) == 5


@pytest.mark.asyncio
async def test_create_plan_renders_recent_turn_summaries_into_the_prompt() -> None:
    llm_service = FakeLLMService(tokens=["unused"], plan_response='{"direct_answer": true}')
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    planner = Planner(llm_service, registry, PromptBuilder())
    summaries = [
        TurnSummary(
            tool_calls=[{"tool": "get_overdue_invoices", "parameters": {"minimum_days": 30}}],
            entities={"customer_name": ["Crestline Holdings"]},
        )
    ]

    await planner.create_plan([], "anything", summaries)

    assert llm_service.last_complete_system is not None
    assert "get_overdue_invoices" in llm_service.last_complete_system
    assert "Crestline Holdings" in llm_service.last_complete_system


@pytest.mark.asyncio
async def test_create_plan_with_no_recent_turn_summaries_omits_the_activity_block() -> None:
    llm_service = FakeLLMService(tokens=["unused"], plan_response='{"direct_answer": true}')
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    planner = Planner(llm_service, registry, PromptBuilder())

    await planner.create_plan([], "anything")

    assert llm_service.last_complete_system is not None
    assert "Recent tool activity" not in llm_service.last_complete_system
