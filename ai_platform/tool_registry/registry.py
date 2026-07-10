from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ToolContext:
    """Per-call context passed to every tool handler alongside its params.

    Handlers that need the database (most finance tools) build their own
    repositories/services from `context.db`; handlers with no I/O
    dependency (e.g. `get_current_date`) simply ignore it. This keeps
    `ToolRegistry` itself DB-free and buildable once at startup (ADR-0004's
    fail-fast requirement) while still giving DB-backed tools a live,
    request-scoped session at call time.
    """

    db: AsyncSession


@dataclass(frozen=True)
class ToolSpec:
    """Declarative metadata for one tool exposed to the LLM planner.

    `handler` is typed to accept `Any` (not the concrete parameters_model)
    so a registry can hold specs for many different tools with different
    parameter/result models without fighting parameter-type variance.
    """

    name: str
    description: str
    parameters_model: type[BaseModel]
    result_model: type[BaseModel]
    handler: Callable[[Any, ToolContext], Awaitable[BaseModel]]


class DuplicateToolError(ValueError):
    """Raised when a tool name is registered more than once."""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise DuplicateToolError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def to_planner_json(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters_model.model_json_schema(),
            }
            for spec in self._tools.values()
        ]
