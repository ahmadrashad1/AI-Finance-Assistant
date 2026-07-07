from __future__ import annotations

import pytest

from ai_platform.memory.conversation_memory import HistoryMessage
from ai_platform.orchestration.planner import Plan, Planner, ToolCall
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.registry import ToolRegistry
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
