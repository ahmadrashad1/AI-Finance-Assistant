from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ConversationSetupTurn(BaseModel):
    user_message: str


class ExpectedTool(BaseModel):
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class Expectations(BaseModel):
    expected_tools: list[ExpectedTool] = Field(default_factory=list)
    expected_clarification: bool | str = False
    expected_out_of_scope: bool = False
    forbidden_content: list[str] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _clarification_and_tools_are_mutually_exclusive(self) -> Expectations:
        expects_clarification = self.expected_clarification is not False
        branches_set = sum(
            [expects_clarification, bool(self.expected_tools), self.expected_out_of_scope]
        )
        if branches_set > 1:
            raise ValueError(
                "expected_clarification, expected_tools, and expected_out_of_scope "
                "are mutually exclusive"
            )
        return self


class EvalCase(BaseModel):
    id: str
    category: str
    tests_memory: bool = False
    conversation_setup: list[ConversationSetupTurn] = Field(default_factory=list)
    user_message: str
    expectations: Expectations
