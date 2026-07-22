from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Final

from ai_platform.llm.service import LLMService
from ai_platform.prompts.planning_prompt import VERSION as PLANNING_PROMPT_VERSION
from ai_platform.prompts.system_prompt import VERSION as SYSTEM_PROMPT_VERSION

DEFAULT_CASSETTES_ROOT = Path(__file__).resolve().parents[2] / "evals" / "cassettes"

# Milestone 12's larger tool catalog (26 tools) means a single planning
# call's tools_json + rules alone uses ~5900 of this Groq account's 6000
# TPM budget - every live call (Phase 1 planning *and* Phase 2 response
# generation are both real Groq calls) needs the account's token bucket to
# have mostly refilled since the last one, or it 413s ("Request too large
# ... tokens per minute"). Throttling only Phase 1 (the big call) isn't
# enough: when tool execution is fast there's little natural delay before
# Phase 2 fires and it 413s instead. So this lives here, in
# RecordingLLMService, which is the single choke point both phases funnel
# through during live recording - never during recorded-mode replay
# (ScriptedLLMService), which makes no network calls and must stay fast.
_LIVE_CALL_MIN_INTERVAL_SECONDS: Final[float] = 100.0
_last_live_call_at: float | None = None


async def _throttle_live_call() -> None:
    global _last_live_call_at
    now = time.monotonic()
    if _last_live_call_at is not None:
        elapsed = now - _last_live_call_at
        remaining = _LIVE_CALL_MIN_INTERVAL_SECONDS - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
    _last_live_call_at = time.monotonic()


# Bounded deliberately low: each retry can itself wait up to ~70s (see
# _rate_limit_wait_seconds), so worst case is _MAX_RETRIES * (~170s) per
# LLM call, and a two-turn case makes up to 4 such calls. A generous retry
# count here turned one already-slow case into a run that looked hung for
# most of an hour. 2 gives one real second chance without letting a single
# case's recording run away.
_MAX_RETRIES: Final[int] = 2


def _rate_limit_wait_seconds(exc: BaseException) -> float | None:
    """If `exc` (an AIError raised by GroqLLMService/AnthropicLLMService)
    wraps a 429/413 token-rate-limit response, return how long to wait
    before retrying - read from the provider's own `retry-after` /
    `x-ratelimit-reset-tokens` response headers rather than guessed, since
    a fixed guess is exactly what `_throttle_live_call`'s fixed interval
    already is, and it isn't always enough (this account's TPM budget is
    tight enough that the natural per-turn processing time - tool
    execution, DB writes - eats an unpredictable amount of the recovery
    window). Returns None for anything that isn't a rate-limit response
    (a genuine error should propagate, not retry).
    """
    cause = exc.__cause__
    response = getattr(cause, "response", None)
    if response is None or getattr(response, "status_code", None) not in (413, 429):
        return None
    headers = getattr(response, "headers", {})
    for header in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        value = headers.get(header)
        if value is None:
            continue
        try:
            return min(float(str(value).rstrip("s")), 70.0)  # capped - bound worst-case retry time
        except ValueError:
            continue
    return 65.0  # rate-limited but no usable header - fall back to a full window


async def _with_rate_limit_retry[T](call: Callable[[], Awaitable[T]]) -> T:
    for attempt in range(_MAX_RETRIES):
        await _throttle_live_call()
        try:
            return await call()
        except Exception as exc:  # noqa: BLE001 - inspected below, re-raised if not a rate limit
            wait = _rate_limit_wait_seconds(exc)
            if wait is None or attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(wait + 5.0)  # +5s safety margin past the reported reset
    raise AssertionError("unreachable")  # pragma: no cover


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
        # Buffered (not truly streamed) under retry: a 413/429 must be
        # caught and retried *before* any chunk reaches the caller, since
        # once tokens have been yielded downstream there's no way to
        # "retry" a partially-delivered reply. This only affects live
        # recording (never recorded-mode replay), where nothing consumes
        # chunks incrementally anyway - the whole reply is captured into
        # one cassette string regardless.
        async def _call() -> list[str]:
            return [chunk async for chunk in self._wrapped.stream_reply(system, history, message)]

        chunks = await _with_rate_limit_retry(_call)
        self.stream_reply_called = True
        self.last_response_text = "".join(chunks)
        for chunk in chunks:
            yield chunk

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        raw = await _with_rate_limit_retry(
            lambda: self._wrapped.complete(system, history, message)
        )
        self.last_plan_response = raw
        return raw
