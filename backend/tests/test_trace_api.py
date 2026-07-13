from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.chat import get_llm_service
from app.main import app
from tests.fakes import FakeLLMService


@pytest.mark.asyncio
async def test_get_trace_reconstructs_a_real_request(clean_db: None) -> None:
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(
        tokens=["Today is 2026-07-08."],
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            chat_response = await client.post(
                "/api/chat",
                json={"session_id": "trace-api-session", "message": "What's today's date?"},
            )
            request_id = chat_response.headers["x-request-id"]

            trace_response = await client.get(f"/api/trace/{request_id}")
    finally:
        app.dependency_overrides.pop(get_llm_service, None)

    assert trace_response.status_code == 200
    body = trace_response.json()
    assert body["request_id"] == request_id
    assert body["plan"]["tool_calls"] == [{"tool": "get_current_date", "parameters": {}}]
    assert body["total_duration_ms"] is not None
    assert [e["tool"] for e in body["tool_executions"]] == ["get_current_date"]
    assert body["tool_executions"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_get_trace_returns_404_for_unknown_request_id(clean_db: None) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trace/no-such-request-id")
    assert response.status_code == 404
