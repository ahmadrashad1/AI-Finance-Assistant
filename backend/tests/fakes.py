from __future__ import annotations

from collections.abc import AsyncIterator


class FakeLLMService:
    """Test double for LLMService. Records the last call's arguments so
    tests can assert on prompt assembly (system prompt, conversation
    history) without hitting the real Anthropic API.
    """

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self.last_system: str | None = None
        self.last_history: list[dict[str, str]] | None = None
        self.last_message: str | None = None

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        self.last_system = system
        self.last_history = history
        self.last_message = message
        for token in self._tokens:
            yield token
