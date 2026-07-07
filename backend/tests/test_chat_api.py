from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.chat import get_llm_service
from app.main import app
from tests.fakes import FakeLLMService


def _parse_sse(body: str) -> list[dict[str, str]]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            events.append(json.loads(block[len("data:") :].strip()))
    return events


@pytest.mark.asyncio
async def test_post_chat_creates_conversation_and_streams_tokens(clean_db: None) -> None:
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(
        tokens=["Hi", " there!"]
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={"session_id": "api-session-1", "message": "Hello"},
            )
        assert response.status_code == 200
        events = _parse_sse(response.text)
        token_events = [e for e in events if e["type"] == "token"]
        done_events = [e for e in events if e["type"] == "done"]
        assert [e["content"] for e in token_events] == ["Hi", " there!"]
        assert len(done_events) == 1

        conversation_id = done_events[0]["conversation_id"]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            history_response = await client.get(
                f"/api/chat/conversations/{conversation_id}/messages"
            )
        assert history_response.status_code == 200
        history = history_response.json()
        assert [(m["role"], m["content"]) for m in history] == [
            ("user", "Hello"),
            ("assistant", "Hi there!"),
        ]
    finally:
        app.dependency_overrides.pop(get_llm_service, None)


@pytest.mark.asyncio
async def test_list_conversations_scoped_to_session(clean_db: None) -> None:
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(tokens=["ok"])
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/chat",
                json={"session_id": "api-session-2", "message": "First conversation"},
            )
            response = await client.get(
                "/api/chat/conversations", params={"session_id": "api-session-2"}
            )
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 1
        assert conversations[0]["title"] == "First conversation"
    finally:
        app.dependency_overrides.pop(get_llm_service, None)


@pytest.mark.asyncio
async def test_empty_message_returns_error_event_not_a_crash(clean_db: None) -> None:
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(tokens=["unused"])
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat", json={"session_id": "api-session-3", "message": "   "}
            )
        assert response.status_code == 200
        events = _parse_sse(response.text)
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["message"] == "Please enter a message."
    finally:
        app.dependency_overrides.pop(get_llm_service, None)
