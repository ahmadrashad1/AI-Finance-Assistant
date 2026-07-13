from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository
from ai_platform.tool_registry.repository import ToolExecutionRepository
from app.db.session import get_db_session

router = APIRouter()


class ToolExecutionTraceEntry(BaseModel):
    tool: str
    parameters: dict[str, Any]
    status: str
    duration_ms: int
    error_message: str | None


class RequestTraceResponse(BaseModel):
    request_id: str
    conversation_id: str
    plan: dict[str, Any]
    planning_prompt_version: str
    system_prompt_version: str
    total_duration_ms: int | None
    tool_executions: list[ToolExecutionTraceEntry]


@router.get("/trace/{request_id}", response_model=RequestTraceResponse)
async def get_trace(
    request_id: str, db: AsyncSession = Depends(get_db_session)
) -> RequestTraceResponse:
    repository = ConversationRepository(db)
    trace = await repository.get_request_trace(request_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"No trace found for request_id {request_id}")

    execution_repository = ToolExecutionRepository(db)
    executions = await execution_repository.list_by_request_id(request_id)

    return RequestTraceResponse(
        request_id=trace.request_id,
        conversation_id=str(trace.conversation_id),
        plan=trace.plan,
        planning_prompt_version=trace.planning_prompt_version,
        system_prompt_version=trace.system_prompt_version,
        total_duration_ms=trace.total_duration_ms,
        tool_executions=[
            ToolExecutionTraceEntry(
                tool=execution.tool, parameters=execution.parameters, status=execution.status,
                duration_ms=execution.duration_ms, error_message=execution.error_message,
            )
            for execution in executions
        ],
    )
