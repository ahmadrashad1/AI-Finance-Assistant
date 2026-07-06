from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from ai_platform.workflow.base import Workflow, WorkflowContext


class RecordingWorkflow(Workflow[str, str]):
    name = "recording"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def initialize(self, input_data: str) -> WorkflowContext:
        self.calls.append("initialize")
        return WorkflowContext(request_id="req-1")

    def validate(self, input_data: str, context: WorkflowContext) -> None:
        self.calls.append("validate")
        if input_data == "":
            raise ValueError("empty input")

    async def execute(self, input_data: str, context: WorkflowContext) -> AsyncIterator[str]:
        self.calls.append("execute")
        yield "a"
        yield "b"

    def log(self, context: WorkflowContext, events: list[str]) -> None:
        self.calls.append(f"log:{events}")

    def evaluate(self, context: WorkflowContext, events: list[str]) -> None:
        self.calls.append("evaluate")

    def complete(self, events: list[str]) -> list[str]:
        self.calls.append("complete")
        return events


@pytest.mark.asyncio
async def test_run_yields_events_in_order() -> None:
    workflow = RecordingWorkflow()
    events = [event async for event in workflow.run("hello")]
    assert events == ["a", "b"]


@pytest.mark.asyncio
async def test_run_calls_lifecycle_steps_in_order() -> None:
    workflow = RecordingWorkflow()
    async for _ in workflow.run("hello"):
        pass
    assert workflow.calls == [
        "initialize",
        "validate",
        "execute",
        "log:['a', 'b']",
        "evaluate",
        "complete",
    ]


@pytest.mark.asyncio
async def test_validate_failure_prevents_execute() -> None:
    workflow = RecordingWorkflow()
    with pytest.raises(ValueError, match="empty input"):
        async for _ in workflow.run(""):
            pass
    assert "execute" not in workflow.calls
