from __future__ import annotations

import json
from typing import Any, Final

from pydantic import BaseModel, Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import HistoryMessage, TurnSummary
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.prompts.planning_prompt import build_planning_prompt
from ai_platform.tool_registry.registry import ToolRegistry
from app.core.errors import AIError

MAX_TOOL_CALLS_PER_PLAN: Final[int] = 5
TOO_MANY_TOOL_CALLS_MESSAGE: Final[str] = (
    "That's a lot to look up at once - could you narrow your question down a bit?"
)


class ToolCall(BaseModel):
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    clarification_needed: str | None = None
    tool_calls: list[ToolCall] | None = None
    direct_answer: bool | None = None
    out_of_scope_refusal: str | None = None

    @model_validator(mode="after")
    def _validate_exactly_one_branch(self) -> Plan:
        branches_set = [
            self.clarification_needed is not None,
            bool(self.tool_calls),
            bool(self.direct_answer),
            self.out_of_scope_refusal is not None,
        ]
        if sum(branches_set) != 1:
            raise ValueError(
                "Plan must set exactly one of clarification_needed, tool_calls, "
                "direct_answer, out_of_scope_refusal"
            )
        return self


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


def _render_recent_activity(summaries: list[TurnSummary]) -> str:
    if not summaries:
        return ""
    lines = ["Recent tool activity:"]
    for summary in reversed(summaries):
        calls = ", ".join(
            f"{call['tool']}({', '.join(f'{k}={v!r}' for k, v in call['parameters'].items())})"
            for call in summary.tool_calls
        )
        if summary.entities:
            entity_parts = [f"{key}: {values}" for key, values in summary.entities.items()]
            entities_text = "; ".join(entity_parts)
        else:
            entities_text = "no entities"
        lines.append(f"- {calls} -> {entities_text}")
    return "\n".join(lines)


class Planner:
    def __init__(
        self, llm_service: LLMService, registry: ToolRegistry, prompt_builder: PromptBuilder
    ) -> None:
        self._llm_service = llm_service
        self._registry = registry
        self._prompt_builder = prompt_builder

    async def create_plan(
        self,
        history: list[HistoryMessage],
        message: str,
        recent_turn_summaries: list[TurnSummary] | None = None,
    ) -> Plan:
        tools_json = json.dumps(self._registry.to_planner_json(), separators=(",", ":"))
        recent_activity = _render_recent_activity(recent_turn_summaries or [])
        system = build_planning_prompt(tools_json, recent_activity)
        prompt = self._prompt_builder.build(system, history)
        raw = await self._llm_service.complete(prompt.system, prompt.messages, message)
        cleaned = _strip_code_fences(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIError(
                "I had trouble figuring out how to answer that. Please try rephrasing."
            ) from exc

        raw_tool_calls = data.get("tool_calls") if isinstance(data, dict) else None
        if isinstance(raw_tool_calls, list) and len(raw_tool_calls) > MAX_TOOL_CALLS_PER_PLAN:
            return Plan(clarification_needed=TOO_MANY_TOOL_CALLS_MESSAGE)

        try:
            return Plan.model_validate(data)
        except PydanticValidationError as exc:
            raise AIError(
                "I had trouble figuring out how to answer that. Please try rephrasing."
            ) from exc
