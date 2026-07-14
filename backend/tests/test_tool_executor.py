from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolContext, ToolRegistry, ToolSpec
from ai_platform.tool_registry.repository import ToolExecutionRepository


class _OkParams(BaseModel):
    value: int = 0


class _OkResult(BaseModel):
    doubled: int


async def _ok_handler(params: _OkParams, context: ToolContext) -> _OkResult:
    return _OkResult(doubled=params.value * 2)


class _BrokenResult(BaseModel):
    required_field: str


async def _crashing_handler(params: _OkParams, context: ToolContext) -> _OkResult:
    raise RuntimeError("boom")


async def _make_conversation(db_session: AsyncSession, session_id: str) -> uuid.UUID:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session(session_id)
    conversation = await repo.create_conversation(session_id)
    await db_session.commit()
    return conversation.id


@pytest.mark.asyncio
async def test_execute_records_success(clean_db: None, db_session: AsyncSession) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-1")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_ok_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-1",
        conversation_id=conversation_id,
        tool="double_it",
        parameters={"value": 21},
    )
    await db_session.commit()

    assert outcome.status == "success"
    assert outcome.result == {"doubled": 42}
    assert outcome.error_message is None

    rows = await execution_repo.list_for_conversation(conversation_id)
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].result == {"doubled": 42}


@pytest.mark.asyncio
async def test_execute_records_unknown_tool_as_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-2")
    registry = ToolRegistry()
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-2", conversation_id=conversation_id, tool="does_not_exist", parameters={}
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert outcome.result is None
    assert "Unknown tool" in (outcome.error_message or "")

    rows = await execution_repo.list_for_conversation(conversation_id)
    assert rows[0].status == "error"


@pytest.mark.asyncio
async def test_execute_records_invalid_parameters_as_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-3")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_ok_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-3",
        conversation_id=conversation_id,
        tool="double_it",
        parameters={"value": "not-a-number"},
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert "Invalid parameters" in (outcome.error_message or "")


@pytest.mark.asyncio
async def test_execute_records_handler_exception_as_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-4")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="crasher",
            description="Always raises.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_crashing_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-4", conversation_id=conversation_id, tool="crasher", parameters={}
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert "boom" in (outcome.error_message or "")


@pytest.mark.asyncio
async def test_execute_records_result_validation_failure_as_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-5")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="mismatched",
            description="Returns the wrong shape.",
            parameters_model=_OkParams,
            result_model=_BrokenResult,
            handler=_ok_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-5", conversation_id=conversation_id, tool="mismatched", parameters={}
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert outcome.result is None


@pytest.mark.asyncio
async def test_execution_row_is_committed_immediately_inside_execute(
    clean_db: None, db_session: AsyncSession
) -> None:
    from app.db.session import get_sessionmaker

    conversation_id = await _make_conversation(db_session, "session-exec-audit")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_ok_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-audit-1",
        conversation_id=conversation_id,
        tool="double_it",
        parameters={"value": 5},
    )
    assert outcome.status == "success"

    # No explicit db_session.commit() here - a genuinely separate
    # connection can only see this row if execute() committed internally.
    async with get_sessionmaker()() as verify_db:
        verify_repo = ToolExecutionRepository(verify_db)
        rows = await verify_repo.list_for_conversation(conversation_id)
        assert len(rows) == 1
        assert rows[0].status == "success"


async def _not_found_handler(params: _OkParams, context: ToolContext) -> _OkResult:
    raise ValueError("Customer not found: Anchor")


@pytest.mark.asyncio
async def test_business_value_error_passes_through_as_user_message(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-friendly-1")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="get_customer",
            description="Fetch a customer.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_not_found_handler,
        )
    )
    executor = ToolExecutor(registry, ToolExecutionRepository(db_session), db_session)

    outcome = await executor.execute(
        request_id="req-friendly-1",
        conversation_id=conversation_id,
        tool="get_customer",
        parameters={"value": 1},
    )

    assert outcome.status == "error"
    # Business message passes through untouched; no internal framing.
    assert outcome.user_error_message == "Customer not found: Anchor"
    # Developer detail is preserved for logs/traces.
    assert "get_customer" in (outcome.error_message or "")


@pytest.mark.asyncio
async def test_unexpected_exception_masked_in_user_message(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-friendly-2")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_crashing_handler,
        )
    )
    executor = ToolExecutor(registry, ToolExecutionRepository(db_session), db_session)

    outcome = await executor.execute(
        request_id="req-friendly-2",
        conversation_id=conversation_id,
        tool="double_it",
        parameters={"value": 1},
    )

    assert outcome.status == "error"
    assert outcome.user_error_message is not None
    assert "boom" not in outcome.user_error_message
    assert "internal error" in outcome.user_error_message
    assert "boom" in (outcome.error_message or "")


@pytest.mark.asyncio
async def test_invalid_parameters_masked_in_user_message(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-friendly-3")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_ok_handler,
        )
    )
    executor = ToolExecutor(registry, ToolExecutionRepository(db_session), db_session)

    outcome = await executor.execute(
        request_id="req-friendly-3",
        conversation_id=conversation_id,
        tool="double_it",
        parameters={"value": "$50,000"},
    )

    assert outcome.status == "error"
    assert outcome.user_error_message is not None
    # Pydantic internals must not reach the user.
    assert "pydantic" not in outcome.user_error_message.lower()
    assert "validation error" not in outcome.user_error_message.lower()
