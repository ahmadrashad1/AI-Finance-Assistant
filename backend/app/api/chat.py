from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from ai_platform.llm.service import AnthropicLLMService, GroqLLMService, LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.prompt_builder import PromptBuilder
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import request_id_ctx_var
from app.db.session import get_db_session

router = APIRouter()


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    conversation_id: str | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    created_at: str


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str


def get_llm_service() -> LLMService:
    settings = get_settings()
    api_key = settings.llm_api_key or ""
    if settings.llm_provider == "groq":
        return GroqLLMService(api_key=api_key, model=settings.llm_model)
    return AnthropicLLMService(api_key=api_key, model=settings.llm_model)


def _format_event(event: ChatEvent) -> str:
    payload: dict[str, str | None] = {"type": event.type}
    if event.content is not None:
        payload["content"] = event.content
    if event.conversation_id is not None:
        payload["conversation_id"] = event.conversation_id
    if event.message is not None:
        payload["message"] = event.message
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chat")
async def post_chat(
    body: ChatMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    llm_service: LLMService = Depends(get_llm_service),
) -> StreamingResponse:
    repository = ConversationRepository(db)
    memory = ConversationMemory(repository)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id=request_id_ctx_var.get(),
    )
    chat_request = ChatRequest(
        session_id=body.session_id,
        message=body.message,
        conversation_id=body.conversation_id,
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in workflow.run(chat_request):
                yield _format_event(event)
            await db.commit()
        except AppError as exc:
            await db.rollback()
            yield _format_event(ChatEvent(type="error", message=exc.user_message))
        except Exception:
            await db.rollback()
            yield _format_event(
                ChatEvent(
                    type="error",
                    message="I couldn't process that right now. Please try again.",
                )
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chat/conversations")
async def list_conversations(
    session_id: str, db: AsyncSession = Depends(get_db_session)
) -> list[ConversationSummary]:
    repository = ConversationRepository(db)
    conversations = await repository.list_conversations(session_id)
    return [
        ConversationSummary(
            id=str(c.id), title=c.title, created_at=c.created_at.isoformat()
        )
        for c in conversations
    ]


@router.get("/chat/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)
) -> list[MessageOut]:
    repository = ConversationRepository(db)
    messages = await repository.get_messages(conversation_id)
    return [
        MessageOut(role=m.role, content=m.content, created_at=m.created_at.isoformat())
        for m in messages
    ]
