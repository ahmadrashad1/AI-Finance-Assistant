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


def _simplify_schema(node: Any) -> Any:
    """Strip planner-irrelevant verbosity from a Pydantic JSON schema.

    Pydantic's `model_json_schema()` is written for tooling that needs a
    fully faithful schema (codegen, OpenAPI, runtime validators) - it pads
    every field with a `title` that just restates the field name, and
    represents `Optional[X]` as `anyOf: [{X}, {"type": "null"}]` plus a
    redundant coercion variant for Decimal fields. None of that helps the
    LLM planner decide which tool/parameters to use; it only inflates the
    token count of a prompt sent on every single planning call. With the
    Phase A domain tools taking the catalog to 26 tools, the unsimplified
    schema pushes a single planning request (~8981 tokens) past this
    account's Groq TPM budget (6000) - every live call fails with a 413
    before the model ever sees the request. This is a pure serialization
    simplification: the *actual* parameter model used to validate tool
    calls is untouched, only what's shown to the planner is condensed.
    """
    if isinstance(node, dict):
        node = dict(node)
        node.pop("title", None)
        if "anyOf" in node:
            variants = [_simplify_schema(v) for v in node.pop("anyOf")]
            non_null = [v for v in variants if v.get("type") != "null"]
            had_null = len(non_null) != len(variants)
            # Pydantic represents Decimal as anyOf[number, pattern-constrained
            # string, null] so plain strings can be coerced at validation time.
            # The planner only needs to know "this is a number".
            if len(non_null) > 1:
                numeric = [v for v in non_null if v.get("type") == "number"]
                if numeric:
                    non_null = numeric
            if len(non_null) == 1:
                merged = non_null[0]
                for key, value in node.items():
                    merged.setdefault(key, value)
                node = merged
            else:
                node["anyOf"] = non_null
            if had_null:
                node["nullable"] = True
        # "default" is always null where present (optionality is already
        # conveyed by "nullable"); "additionalProperties"/"minimum" are
        # validation-time concerns the planner doesn't need to see.
        node.pop("pattern", None)
        node.pop("default", None)
        node.pop("additionalProperties", None)
        node.pop("minimum", None)
        return {key: _simplify_schema(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_simplify_schema(item) for item in node]
    return node


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
                "parameters": _simplify_schema(spec.parameters_model.model_json_schema()),
            }
            for spec in self._tools.values()
        ]
