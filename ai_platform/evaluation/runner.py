from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.cassette import (
    RecordingLLMService,
    ScriptedLLMService,
    load_cassette,
    save_cassette,
)
from ai_platform.evaluation.scoring import ActualToolCall, CaseOutcome
from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository


class CaseStale(Exception):  # noqa: N818 -- name fixed by the Task 10 interface spec
    """Raised in `recorded` mode when a turn's cassette is missing -
    either the prompt versions changed since it was recorded, or it was
    never recorded at all. Run with `--record` to (re)generate it.
    """


def _build_workflow(
    db: AsyncSession, registry: ToolRegistry, llm_service: LLMService, request_id: str
) -> ChatWorkflow:
    repository = ConversationRepository(db)
    memory = ConversationMemory(repository)
    prompt_builder = PromptBuilder()
    execution_repository = ToolExecutionRepository(db)
    tool_executor = ToolExecutor(registry, execution_repository, db)
    planner = Planner(llm_service, registry, prompt_builder)
    return ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=planner,
        execution_planner=ExecutionPlanner(),
        tool_executor=tool_executor,
        request_id=request_id,
    )


async def _run_turn(
    db: AsyncSession,
    registry: ToolRegistry,
    *,
    case_id: str,
    turn: int,
    user_message: str,
    conversation_id: str | None,
    mode: str,
    real_llm_service: LLMService | None,
    record: bool,
    cassettes_root: Path | None,
    run_token: str,
) -> tuple[str, list[ChatEvent], bool]:
    request_id = f"eval-{case_id}-{run_token}-turn{turn}"
    recorder: RecordingLLMService | None = None

    if mode == "live":
        if real_llm_service is None:
            raise ValueError("live mode requires a real_llm_service")
        recorder = RecordingLLMService(real_llm_service)
        llm_service: LLMService = recorder
    else:
        cassette = load_cassette(case_id, turn, cassettes_root=cassettes_root)
        if cassette is None:
            raise CaseStale(
                f"{case_id} turn {turn}: no cassette for the current prompt version - "
                "run with --record"
            )
        llm_service = ScriptedLLMService(
            plan_response=cassette["plan_response"], response_text=cassette["response_text"]
        )

    workflow = _build_workflow(db, registry, llm_service, request_id)
    events = [
        e
        async for e in workflow.run(
            ChatRequest(
                session_id=f"eval-{case_id}", message=user_message, conversation_id=conversation_id
            )
        )
    ]
    await db.commit()

    stream_reply_called = getattr(llm_service, "stream_reply_called", False)

    if record and recorder is not None:
        if recorder.last_plan_response is None:
            raise RuntimeError(f"{case_id} turn {turn}: planner was never called while recording")
        save_cassette(
            case_id, turn,
            plan_response=recorder.last_plan_response,
            response_text=recorder.last_response_text or "",
            cassettes_root=cassettes_root,
        )

    new_conversation_id = conversation_id
    for event in events:
        if event.type == "done" and event.conversation_id is not None:
            new_conversation_id = event.conversation_id
    if new_conversation_id is None:
        raise RuntimeError(f"{case_id} turn {turn}: workflow never completed")
    return new_conversation_id, events, stream_reply_called


async def run_case(
    db: AsyncSession,
    registry: ToolRegistry,
    case: EvalCase,
    *,
    mode: str = "recorded",
    record: bool = False,
    real_llm_service: LLMService | None = None,
    cassettes_root: Path | None = None,
) -> CaseOutcome:
    # Unique per run_case invocation - not per case_id - so that running the
    # same case twice in one process/database (e.g. live-record then
    # recorded-replay in the same test) doesn't have the second run's
    # tool-execution lookup pick up rows left behind by the first run: both
    # would otherwise share the identical "eval-{case_id}-turn{turn}"
    # request_id and collide in ToolExecutionRepository.list_by_request_id.
    run_token = uuid.uuid4().hex[:8]

    conversation_id: str | None = None
    turn = 0
    for setup_turn in case.conversation_setup:
        conversation_id, _, _ = await _run_turn(
            db, registry, case_id=case.id, turn=turn, user_message=setup_turn.user_message,
            conversation_id=conversation_id, mode=mode, real_llm_service=real_llm_service,
            record=record, cassettes_root=cassettes_root, run_token=run_token,
        )
        turn += 1

    conversation_id, events, stream_reply_called = await _run_turn(
        db, registry, case_id=case.id, turn=turn, user_message=case.user_message,
        conversation_id=conversation_id, mode=mode, real_llm_service=real_llm_service,
        record=record, cassettes_root=cassettes_root, run_token=run_token,
    )

    response_text = "".join(
        e.content for e in events if e.type == "token" and e.content is not None
    )
    clarification = None if stream_reply_called else (response_text or None)

    execution_repository = ToolExecutionRepository(db)
    executions = await execution_repository.list_by_request_id(
        f"eval-{case.id}-{run_token}-turn{turn}"
    )
    tool_calls = [ActualToolCall(tool=e.tool, parameters=e.parameters) for e in executions]

    return CaseOutcome(
        tool_calls=tool_calls, response_text=response_text, clarification=clarification
    )
