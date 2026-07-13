from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path

from ai_platform.llm.service import LLMService
from ai_platform.prompts.planning_prompt import VERSION as PLANNING_PROMPT_VERSION
from ai_platform.prompts.system_prompt import VERSION as SYSTEM_PROMPT_VERSION

DEFAULT_CASSETTES_ROOT = Path(__file__).resolve().parents[2] / "evals" / "cassettes"


def prompt_version_hash() -> str:
    raw = f"{PLANNING_PROMPT_VERSION}:{SYSTEM_PROMPT_VERSION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def cassette_path(case_id: str, turn: int, *, cassettes_root: Path | None = None) -> Path:
    root = cassettes_root if cassettes_root is not None else DEFAULT_CASSETTES_ROOT
    return root / f"{case_id}__turn{turn}__{prompt_version_hash()}.json"


def load_cassette(
    case_id: str, turn: int, *, cassettes_root: Path | None = None
) -> dict[str, str] | None:
    path = cassette_path(case_id, turn, cassettes_root=cassettes_root)
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data: dict[str, str] = json.load(handle)
    return data


def save_cassette(
    case_id: str,
    turn: int,
    *,
    plan_response: str,
    response_text: str,
    cassettes_root: Path | None = None,
) -> None:
    root = cassettes_root if cassettes_root is not None else DEFAULT_CASSETTES_ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = cassette_path(case_id, turn, cassettes_root=cassettes_root)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {"plan_response": plan_response, "response_text": response_text}, handle, indent=2
        )


class ScriptedLLMService:
    """Production LLMService implementation that replays fixed text
    instead of calling a real model - the third LLMService alongside
    AnthropicLLMService/GroqLLMService, used only by the evaluation
    runner's `recorded` mode. Distinct from `backend/tests/fakes.py`'s
    FakeLLMService, which is test-only and never imported from
    ai_platform.
    """

    def __init__(self, plan_response: str, response_text: str) -> None:
        self._plan_response = plan_response
        self._response_text = response_text
        self.stream_reply_called = False

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        self.stream_reply_called = True
        yield self._response_text

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        return self._plan_response


class RecordingLLMService:
    """Wraps a real LLMService, delegating every call unchanged while
    buffering the exact strings returned, so `--record` can persist them
    to a cassette after the turn completes.
    """

    def __init__(self, wrapped: LLMService) -> None:
        self._wrapped = wrapped
        self.stream_reply_called = False
        self.last_plan_response: str | None = None
        self.last_response_text: str | None = None

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        self.stream_reply_called = True
        chunks: list[str] = []
        async for chunk in self._wrapped.stream_reply(system, history, message):
            chunks.append(chunk)
            yield chunk
        self.last_response_text = "".join(chunks)

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        raw = await self._wrapped.complete(system, history, message)
        self.last_plan_response = raw
        return raw
