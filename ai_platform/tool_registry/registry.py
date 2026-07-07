from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


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
    handler: Callable[[Any], Awaitable[BaseModel]]


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
