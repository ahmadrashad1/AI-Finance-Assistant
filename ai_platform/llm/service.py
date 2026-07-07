from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

import anthropic
from anthropic import AsyncAnthropic

from app.core.errors import AIError

CHAT_MAX_TOKENS = 1024


class LLMService(Protocol):
    def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]: ...


class AnthropicLLMService:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        messages = [*history, {"role": "user", "content": message}]
        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=CHAT_MAX_TOKENS,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIConnectionError as exc:
            raise AIError("I couldn't reach the assistant right now. Please try again.") from exc
        except anthropic.RateLimitError as exc:
            raise AIError("The assistant is busy right now. Please try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise AIError("I couldn't process that right now. Please try again.") from exc
