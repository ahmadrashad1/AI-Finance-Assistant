from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Generic, TypeVar

InputT = TypeVar("InputT")
EventT = TypeVar("EventT")


@dataclass
class WorkflowContext:
    """Carries request-scoped identifiers through a workflow run."""

    request_id: str | None
    conversation_id: str | None = None


class Workflow(ABC, Generic[InputT, EventT]):
    """Base class enforcing the mandatory lifecycle: Initialize -> Validate
    -> Execute -> Log -> Evaluate -> Complete. No step may be skipped.
    """

    name: str

    @abstractmethod
    def initialize(self, input_data: InputT) -> WorkflowContext:
        """Build the request context for this run."""

    @abstractmethod
    def validate(self, input_data: InputT, context: WorkflowContext) -> None:
        """Raise if input_data is invalid. No return value on success."""

    @abstractmethod
    def execute(self, input_data: InputT, context: WorkflowContext) -> AsyncIterator[EventT]:
        """Do the work, yielding zero or more events as they become available."""

    @abstractmethod
    def log(self, context: WorkflowContext, events: list[EventT]) -> None:
        """Emit a structured log line summarizing this run."""

    def evaluate(self, context: WorkflowContext, events: list[EventT]) -> None:
        """Optional evaluation hook. No-op by default."""
        return None

    def complete(self, events: list[EventT]) -> list[EventT]:
        """Final hook. Returns the collected events by default."""
        return events

    async def run(self, input_data: InputT) -> AsyncIterator[EventT]:
        context = self.initialize(input_data)
        self.validate(input_data, context)
        collected: list[EventT] = []
        async for event in self.execute(input_data, context):
            collected.append(event)
            yield event
        self.log(context, collected)
        self.evaluate(context, collected)
        self.complete(collected)
