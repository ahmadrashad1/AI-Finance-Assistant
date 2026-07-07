from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatRequest, ChatWorkflow
from ai_platform.orchestration.prompt_builder import PromptBuilder
from app.core.errors import ValidationError
from tests.fakes import FakeLLMService


def _make_workflow(
    db_session: AsyncSession, llm_service: FakeLLMService
) -> tuple[ChatWorkflow, ConversationRepository]:
    repository = ConversationRepository(db_session)
    memory = ConversationMemory(repository)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id="req-test",
    )
    return workflow, repository


@pytest.mark.asyncio
async def test_new_conversation_streams_tokens_and_persists_both_messages(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(tokens=["Hel", "lo!"])
    workflow, repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-1", message="Hi there")
    events = [event async for event in workflow.run(request)]
    await db_session.commit()

    token_events = [e for e in events if e.type == "token"]
    done_events = [e for e in events if e.type == "done"]
    assert [e.content for e in token_events] == ["Hel", "lo!"]
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
    workflow, repository = _make_workflow(db_session, llm_service)

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
    workflow, _repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-3", message="   ")
    with pytest.raises(ValidationError):
        async for _ in workflow.run(request):
            pass

    assert llm_service.last_message is None


@pytest.mark.asyncio
async def test_context_vars_set_during_run_and_reset_after(
    clean_db: None, db_session: AsyncSession
) -> None:
    from app.core.logging import conversation_id_ctx_var, workflow_ctx_var

    llm_service = FakeLLMService(tokens=["ok"])
    workflow, _repository = _make_workflow(db_session, llm_service)

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
