from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.models import ToolExecutionModel


class ToolExecutionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_execution(
        self,
        *,
        request_id: str,
        conversation_id: uuid.UUID,
        tool: str,
        parameters: dict[str, Any],
        result: dict[str, Any] | None,
        duration_ms: int,
        status: str,
        error_message: str | None,
    ) -> ToolExecutionModel:
        execution = ToolExecutionModel(
            id=uuid.uuid4(),
            request_id=request_id,
            conversation_id=conversation_id,
            tool=tool,
            parameters=parameters,
            result=result,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
        )
        self._db.add(execution)
        await self._db.flush()
        return execution

    async def list_for_conversation(self, conversation_id: uuid.UUID) -> list[ToolExecutionModel]:
        stmt = (
            select(ToolExecutionModel)
            .where(ToolExecutionModel.conversation_id == conversation_id)
            .order_by(ToolExecutionModel.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
