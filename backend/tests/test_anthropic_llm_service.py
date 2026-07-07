from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import anthropic
import httpx
import pytest

from ai_platform.llm.service import AnthropicLLMService
from app.core.errors import AIError


class _FakeStream:
    def __init__(self, tokens: list[str], error: Exception | None = None) -> None:
        self._tokens = tokens
        self._error = error

    async def __aenter__(self) -> _FakeStream:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    @property
    async def text_stream(self) -> AsyncIterator[str]:  # type: ignore[override]
        if self._error is not None:
            raise self._error
        for token in self._tokens:
            yield token


def _fake_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.asyncio
async def test_stream_reply_yields_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AnthropicLLMService(api_key="test-key", model="claude-haiku-4-5")

    def fake_stream(**kwargs: Any) -> _FakeStream:
        return _FakeStream(tokens=["Hel", "lo"])

    monkeypatch.setattr(service._client.messages, "stream", fake_stream)

    tokens = [t async for t in service.stream_reply("system", [], "hi")]
    assert tokens == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_rate_limit_error_becomes_ai_error(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AnthropicLLMService(api_key="test-key", model="claude-haiku-4-5")

    def fake_stream(**kwargs: Any) -> _FakeStream:
        return _FakeStream(
            tokens=[],
            error=anthropic.RateLimitError(
                message="rate limited",
                response=httpx.Response(429, request=_fake_request()),
                body=None,
            ),
        )

    monkeypatch.setattr(service._client.messages, "stream", fake_stream)

    with pytest.raises(AIError):
        async for _ in service.stream_reply("system", [], "hi"):
            pass
