from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatRequest, ChatWorkflow
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry, ToolSpec
from ai_platform.tool_registry.repository import ToolExecutionRepository
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from app.core.errors import ValidationError
from tests.fakes import FakeLLMService


def _make_workflow(
    db_session: AsyncSession,
    llm_service: FakeLLMService,
    extra_tools: list[ToolSpec] | None = None,
) -> tuple[ChatWorkflow, ConversationRepository, ToolExecutionRepository]:
    repository = ConversationRepository(db_session)
    memory = ConversationMemory(repository)
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    for tool in extra_tools or []:
        registry.register(tool)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
    prompt_builder = PromptBuilder()
    planner = Planner(llm_service, registry, prompt_builder)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=planner,
        tool_executor=tool_executor,
        request_id="req-test",
    )
    return workflow, repository, execution_repository


@pytest.mark.asyncio
async def test_new_conversation_streams_tokens_and_persists_both_messages(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(tokens=["Hel", "lo!"])
    workflow, repository, _execution_repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-1", message="Hi there")
    events = [event async for event in workflow.run(request)]
    await db_session.commit()

    token_events = [e for e in events if e.type == "token"]
    tool_call_events = [e for e in events if e.type == "tool_call"]
    done_events = [e for e in events if e.type == "done"]
    assert [e.content for e in token_events] == ["Hel", "lo!"]
    assert tool_call_events == []
    assert len(done_events) == 1
    assert done_events[0].conversation_id is not None

    conversation_id = uuid.UUID(done_events[0].conversation_id)
    messages = await repository.get_messages(conversation_id)
    assert [(m.role, m.content) for m in messages] == [
        ("user", "Hi there"),
        ("assistant", "Hello!"),
    ]


@pytest.mark.asyncio
async def test_existing_conversation_includes_prior_history_in_prompt(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(tokens=["Sure."])
    workflow, repository, _execution_repository = _make_workflow(db_session, llm_service)

    await repository.get_or_create_session("session-wf-2")
    conversation = await repository.create_conversation("session-wf-2")
    await repository.add_message(conversation.id, "user", "What's my name?")
    await repository.add_message(conversation.id, "assistant", "I don't know yet.")
    await db_session.commit()

    request = ChatRequest(
        session_id="session-wf-2",
        message="It's Alex.",
        conversation_id=str(conversation.id),
    )
    async for _ in workflow.run(request):
        pass
    await db_session.commit()

    assert llm_service.last_history == [
        {"role": "user", "content": "What's my name?"},
        {"role": "assistant", "content": "I don't know yet."},
    ]
    assert llm_service.last_message == "It's Alex."


@pytest.mark.asyncio
async def test_empty_message_is_rejected_before_any_llm_call(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(tokens=["should not be used"])
    workflow, _repository, _execution_repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-3", message="   ")
    with pytest.raises(ValidationError):
        async for _ in workflow.run(request):
            pass

    assert llm_service.last_message is None
    assert llm_service.last_complete_message is None


@pytest.mark.asyncio
async def test_context_vars_set_during_run_and_reset_after(
    clean_db: None, db_session: AsyncSession
) -> None:
    from app.core.logging import conversation_id_ctx_var, workflow_ctx_var

    llm_service = FakeLLMService(tokens=["ok"])
    workflow, _repository, _execution_repository = _make_workflow(db_session, llm_service)

    assert conversation_id_ctx_var.get() is None
    assert workflow_ctx_var.get() is None

    seen_workflow_during_run: str | None = None
    seen_conversation_id_during_run: str | None = None
    async for event in workflow.run(ChatRequest(session_id="session-wf-ctx", message="hi")):
        if event.type == "token":
            seen_workflow_during_run = workflow_ctx_var.get()
            seen_conversation_id_during_run = conversation_id_ctx_var.get()
    await db_session.commit()

    assert seen_workflow_during_run == "chat"
    assert seen_conversation_id_during_run is not None
    assert conversation_id_ctx_var.get() is None
    assert workflow_ctx_var.get() is None


@pytest.mark.asyncio
async def test_tool_calls_branch_executes_tool_and_persists_execution_row(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(
        tokens=["Today is the date."],
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
    )
    workflow, _repository, execution_repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-4", message="What's today's date?")
    events = [event async for event in workflow.run(request)]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_current_date"]

    done_events = [e for e in events if e.type == "done"]
    conversation_id = uuid.UUID(done_events[0].conversation_id or "")

    executions = await execution_repository.list_for_conversation(conversation_id)
    assert len(executions) == 1
    assert executions[0].tool == "get_current_date"
    assert executions[0].status == "success"
    assert executions[0].result is not None
    assert "date" in executions[0].result

    assert llm_service.last_message is not None
    assert "Tool results" in llm_service.last_message


@pytest.mark.asyncio
async def test_clarification_branch_skips_tool_execution_and_phase_two(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(
        tokens=["should not be used"],
        plan_response='{"clarification_needed": "Which invoices do you mean?"}',
    )
    workflow, repository, execution_repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-5", message="Show invoices")
    events = [event async for event in workflow.run(request)]
    await db_session.commit()

    assert [e.type for e in events] == ["token", "done"]
    assert events[0].content == "Which invoices do you mean?"
    assert llm_service.last_message is None

    done_event = events[1]
    conversation_id = uuid.UUID(done_event.conversation_id or "")
    messages = await repository.get_messages(conversation_id)
    assert [(m.role, m.content) for m in messages] == [
        ("user", "Show invoices"),
        ("assistant", "Which invoices do you mean?"),
    ]

    executions = await execution_repository.list_for_conversation(conversation_id)
    assert executions == []


@pytest.mark.asyncio
async def test_large_list_tool_result_is_capped_before_reaching_the_llm(
    clean_db: None, db_session: AsyncSession
) -> None:
    import json as json_module

    from pydantic import BaseModel

    from ai_platform.tool_registry.registry import ToolContext

    class _BigListParams(BaseModel):
        pass

    class _BigListResult(BaseModel):
        items: list[int]

    async def _big_list_handler(params: _BigListParams, context: ToolContext) -> _BigListResult:
        return _BigListResult(items=list(range(15)))

    big_list_tool = ToolSpec(
        name="big_list",
        description="Returns a big list.",
        parameters_model=_BigListParams,
        result_model=_BigListResult,
        handler=_big_list_handler,
    )
    llm_service = FakeLLMService(
        tokens=["ok"],
        plan_response='{"tool_calls": [{"tool": "big_list", "parameters": {}}]}',
    )
    workflow, _repository, _execution_repository = _make_workflow(
        db_session, llm_service, extra_tools=[big_list_tool]
    )

    request = ChatRequest(session_id="session-wf-cap", message="give me the big list")
    async for _ in workflow.run(request):
        pass
    await db_session.commit()

    assert llm_service.last_message is not None
    tool_results_json = llm_service.last_message.split("\n\n[Tool results — use only this data]\n")[
        1
    ]
    payload = json_module.loads(tool_results_json)
    assert payload[0]["result"]["items"] == list(range(10))
    assert payload[0]["result"]["_truncated"] is True
    assert payload[0]["result"]["_items_omitted_count"] == 5
