from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext, ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from ai_platform.tool_registry.result_validator import ResultValidationError, validate_result

logger = logging.getLogger("ai_platform.tool_executor")


@dataclass
class ToolExecutionOutcome:
    tool: str
    parameters: dict[str, Any]
    result: dict[str, Any] | None
    status: str
    error_message: str | None
    duration_ms: int
    # Friendly, user-safe error text for the Phase-2 prompt. The raw
    # error_message keeps flowing to logs and tool_executions/traces.
    user_error_message: str | None = None


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        execution_repository: ToolExecutionRepository,
        db: AsyncSession,
    ) -> None:
        self._registry = registry
        self._execution_repository = execution_repository
        self._db = db

    async def execute(
        self,
        *,
        request_id: str | None,
        conversation_id: uuid.UUID,
        tool: str,
        parameters: dict[str, Any],
    ) -> ToolExecutionOutcome:
        start = time.monotonic()
        result: dict[str, Any] | None = None
        status = "success"
        error_message: str | None = None
        user_error_message: str | None = None

        spec = self._registry.get(tool)
        if spec is None:
            status = "error"
            error_message = f"Unknown tool: {tool}"
            user_error_message = "That capability isn't available."
        else:
            try:
                validated_params = spec.parameters_model.model_validate(parameters)
            except PydanticValidationError as exc:
                status = "error"
                error_message = f"Invalid parameters for tool '{tool}': {exc}"
                user_error_message = (
                    "One of the values in this request wasn't in a usable format."
                )
            else:
                try:
                    context = ToolContext(db=self._db)
                    raw_result = await spec.handler(validated_params, context)
                except ValueError as exc:
                    # Business errors carry user-appropriate messages by
                    # convention (e.g. "Customer not found: Anchor").
                    status = "error"
                    error_message = f"Tool '{tool}' failed: {exc}"
                    user_error_message = str(exc)
                except Exception as exc:
                    status = "error"
                    error_message = f"Tool '{tool}' failed: {exc}"
                    user_error_message = "This lookup failed because of an internal error."
                else:
                    try:
                        result = validate_result(spec, raw_result.model_dump())
                    except ResultValidationError as exc:
                        status = "error"
                        error_message = str(exc)
                        user_error_message = (
                            "This lookup returned data that failed an internal check."
                        )

        duration_ms = int((time.monotonic() - start) * 1000)

        await self._execution_repository.record_execution(
            request_id=request_id or "unknown",
            conversation_id=conversation_id,
            tool=tool,
            parameters=parameters,
            result=result,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
        )
        await self._db.commit()
        logger.info(
            "tool execution complete: tool=%s status=%s duration_ms=%d", tool, status, duration_ms
        )
        return ToolExecutionOutcome(
            tool=tool,
            parameters=parameters,
            result=result,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            user_error_message=user_error_message,
        )
