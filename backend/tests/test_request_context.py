import logging
import re

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.logging import request_id_ctx_var
from app.middleware.request_context import RequestContextMiddleware

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class _CapturingHandler(logging.Handler):
    """Records the request_id contextvar's value at the moment each record is emitted."""

    def __init__(self) -> None:
        super().__init__()
        self.request_ids_at_emit: list[str | None] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.request_ids_at_emit.append(request_id_ctx_var.get())


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    return app


@pytest.mark.asyncio
async def test_generates_a_request_id_when_none_provided() -> None:
    transport = ASGITransport(app=build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ping")
    assert UUID_RE.match(response.headers["x-request-id"])


@pytest.mark.asyncio
async def test_echoes_a_client_provided_request_id() -> None:
    transport = ASGITransport(app=build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ping", headers={"X-Request-ID": "client-supplied-id"})
    assert response.headers["x-request-id"] == "client-supplied-id"


@pytest.mark.asyncio
async def test_completion_log_line_is_emitted_while_request_id_is_still_set() -> None:
    request_logger = logging.getLogger("app.request")
    handler = _CapturingHandler()
    request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)
    try:
        transport = ASGITransport(app=build_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/ping", headers={"X-Request-ID": "log-during-request"})
    finally:
        request_logger.removeHandler(handler)

    assert handler.request_ids_at_emit, "expected the middleware to log a completion line"
    assert handler.request_ids_at_emit[-1] == "log-during-request"
