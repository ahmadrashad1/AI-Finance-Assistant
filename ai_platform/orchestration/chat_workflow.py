from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextvars import Token
from dataclasses import dataclass

from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.orchestration.result_shaping import cap_result_for_prompt
from ai_platform.prompts.system_prompt import SYSTEM_PROMPT
from ai_platform.tool_registry.executor import ToolExecutionOutcome, ToolExecutor
from ai_platform.workflow.base import Workflow, WorkflowContext
from app.core.errors import ValidationError
from app.core.logging import conversation_id_ctx_var, workflow_ctx_var

logger = logging.getLogger("ai_platform.chat")


@dataclass
class ChatRequest:
    session_id: str
    message: str
    conversation_id: str | None = None


@dataclass
class ChatEvent:
    type: str  # "token" | "tool_call" | "done" | "error"
    content: str | None = None
    conversation_id: str | None = None
    message: str | None = None
    tool: str | None = None


def _build_response_message(message: str, outcomes: list[ToolExecutionOutcome]) -> str:
    if not outcomes:
        return message
    results = [
        {
            "tool": outcome.tool,
            "status": outcome.status,
            "result": cap_result_for_prompt(outcome.result),
            "error": outcome.error_message,
        }
        for outcome in outcomes
    ]
    return f"{message}\n\n[Tool results — use only this data]\n{json.dumps(results)}"


class ChatWorkflow(Workflow[ChatRequest, ChatEvent]):
    name = "chat"

    def __init__(
        self,
        repository: ConversationRepository,
        memory: ConversationMemory,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        planner: Planner,
        tool_executor: ToolExecutor,
        request_id: str | None,
    ) -> None:
        self._repository = repository
        self._memory = memory
        self._prompt_builder = prompt_builder
        self._llm_service = llm_service
        self._planner = planner
        self._tool_executor = tool_executor
        self._request_id = request_id

    def initialize(self, input_data: ChatRequest) -> WorkflowContext:
        return WorkflowContext(
            request_id=self._request_id, conversation_id=input_data.conversation_id
        )

    def validate(self, input_data: ChatRequest, context: WorkflowContext) -> None:
        if not input_data.message.strip():
            raise ValidationError("Please enter a message.")

    async def execute(
        self, input_data: ChatRequest, context: WorkflowContext
    ) -> AsyncIterator[ChatEvent]:
        workflow_token = workflow_ctx_var.set(self.name)
        conversation_token: Token[str | None] | None = None
        try:
            await self._repository.get_or_create_session(input_data.session_id)

            if input_data.conversation_id is None:
                conversation = await self._repository.create_conversation(input_data.session_id)
                conversation_id = conversation.id
            else:
                conversation_id = uuid.UUID(input_data.conversation_id)
            context.conversation_id = str(conversation_id)
            conversation_token = conversation_id_ctx_var.set(context.conversation_id)

            history = await self._memory.get_context_window(conversation_id)
            await self._repository.add_message(conversation_id, "user", input_data.message)

            plan = await self._planner.create_plan(history, input_data.message)

            if plan.clarification_needed is not None:
                yield ChatEvent(type="token", content=plan.clarification_needed)
                await self._repository.add_message(
                    conversation_id, "assistant", plan.clarification_needed
                )
                yield ChatEvent(type="done", conversation_id=str(conversation_id))
                return

            outcomes: list[ToolExecutionOutcome] = []
            for tool_call in plan.tool_calls or []:
                yield ChatEvent(type="tool_call", tool=tool_call.tool)
                outcome = await self._tool_executor.execute(
                    request_id=self._request_id,
                    conversation_id=conversation_id,
                    tool=tool_call.tool,
                    parameters=tool_call.parameters,
                )
                outcomes.append(outcome)

            prompt = self._prompt_builder.build(SYSTEM_PROMPT, history)
            llm_message = _build_response_message(input_data.message, outcomes)

            assistant_reply: list[str] = []
            async for token in self._llm_service.stream_reply(
                prompt.system, prompt.messages, llm_message
            ):
                assistant_reply.append(token)
                yield ChatEvent(type="token", content=token)

            await self._repository.add_message(
                conversation_id, "assistant", "".join(assistant_reply)
            )
            yield ChatEvent(type="done", conversation_id=str(conversation_id))
        finally:
            if conversation_token is not None:
                conversation_id_ctx_var.reset(conversation_token)
            workflow_ctx_var.reset(workflow_token)

    def log(self, context: WorkflowContext, events: list[ChatEvent]) -> None:
        token_count = sum(1 for e in events if e.type == "token")
        tool_call_count = sum(1 for e in events if e.type == "tool_call")
        logger.info("chat turn complete: %d tokens, %d tool calls", token_count, tool_call_count)
