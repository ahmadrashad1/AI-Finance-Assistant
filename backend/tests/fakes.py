from __future__ import annotations

from collections.abc import AsyncIterator


class FakeLLMService:
    """Test double for LLMService. Records the last call's arguments so
    tests can assert on prompt assembly (system prompt, conversation
    history) without hitting a real LLM provider.
    """

    def __init__(
        self,
        tokens: list[str],
        plan_response: str = '{"direct_answer": true}',
        fail_stream_with: Exception | None = None,
    ) -> None:
        self._tokens = tokens
        self._plan_response = plan_response
        self._fail_stream_with = fail_stream_with
        self.last_system: str | None = None
        self.last_history: list[dict[str, str]] | None = None
        self.last_message: str | None = None
        self.last_complete_system: str | None = None
        self.last_complete_history: list[dict[str, str]] | None = None
        self.last_complete_message: str | None = None

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        self.last_system = system
        self.last_history = history
        self.last_message = message
        if self._fail_stream_with is not None:
            raise self._fail_stream_with
        for token in self._tokens:
            yield token

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        self.last_complete_system = system
        self.last_complete_history = history
        self.last_complete_message = message
        return self._plan_response
