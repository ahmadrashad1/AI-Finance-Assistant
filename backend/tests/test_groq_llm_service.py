from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import groq
import httpx
import pytest

from ai_platform.llm.service import GroqLLMService
from app.core.errors import AIError


class _FakeDelta:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content: str | None) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeStream:
    def __init__(self, tokens: list[str], error: Exception | None = None) -> None:
        self._tokens = tokens
        self._error = error

    def __aiter__(self) -> AsyncIterator[_FakeChunk]:
        return self._generate()

    async def _generate(self) -> AsyncIterator[_FakeChunk]:
        if self._error is not None:
            raise self._error
        for token in self._tokens:
            yield _FakeChunk(token)


def _fake_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


@pytest.mark.asyncio
async def test_stream_reply_yields_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    service = GroqLLMService(api_key="test-key", model="llama-3.1-8b-instant")

    async def fake_create(**kwargs: Any) -> _FakeStream:
        return _FakeStream(tokens=["Hel", "lo"])

    monkeypatch.setattr(service._client.chat.completions, "create", fake_create)

    tokens = [t async for t in service.stream_reply("system", [], "hi")]
    assert tokens == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_rate_limit_error_becomes_ai_error(monkeypatch: pytest.MonkeyPatch) -> None:
    service = GroqLLMService(api_key="test-key", model="llama-3.1-8b-instant")

    async def fake_create(**kwargs: Any) -> _FakeStream:
        return _FakeStream(
            tokens=[],
            error=groq.RateLimitError(
                message="rate limited",
                response=httpx.Response(429, request=_fake_request()),
                body=None,
            ),
        )

    monkeypatch.setattr(service._client.chat.completions, "create", fake_create)

    with pytest.raises(AIError):
        async for _ in service.stream_reply("system", [], "hi"):
            pass
