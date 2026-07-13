from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ai_platform.evaluation.cassette import (
    RecordingLLMService,
    ScriptedLLMService,
    cassette_path,
    load_cassette,
    prompt_version_hash,
    save_cassette,
)


def test_prompt_version_hash_is_stable_and_twelve_hex_chars() -> None:
    first = prompt_version_hash()
    second = prompt_version_hash()
    assert first == second
    assert len(first) == 12
    assert all(c in "0123456789abcdef" for c in first)


def test_prompt_version_hash_changes_when_a_version_changes() -> None:
    with patch("ai_platform.evaluation.cassette.PLANNING_PROMPT_VERSION", "9.9.9"):
        changed = prompt_version_hash()
    assert changed != prompt_version_hash()


def test_load_cassette_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert load_cassette("no-such-case", 0, cassettes_root=tmp_path) is None


def test_save_then_load_cassette_round_trips(tmp_path: Path) -> None:
    save_cassette(
        "case-1", 0,
        plan_response='{"tool_calls": []}', response_text="Here you go.",
        cassettes_root=tmp_path,
    )

    loaded = load_cassette("case-1", 0, cassettes_root=tmp_path)

    assert loaded == {"plan_response": '{"tool_calls": []}', "response_text": "Here you go."}


def test_cassette_path_includes_case_id_turn_and_hash(tmp_path: Path) -> None:
    path = cassette_path("case-1", 2, cassettes_root=tmp_path)
    assert path.parent == tmp_path
    assert path.name == f"case-1__turn2__{prompt_version_hash()}.json"


@pytest.mark.asyncio
async def test_scripted_llm_service_replays_fixed_content() -> None:
    service = ScriptedLLMService(
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
    )

    assert service.stream_reply_called is False
    plan_raw = await service.complete("system", [], "What's today?")
    assert plan_raw == '{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}'

    chunks = [chunk async for chunk in service.stream_reply("system", [], "What's today?")]
    assert chunks == ["Today is Tuesday."]
    assert service.stream_reply_called is True


@pytest.mark.asyncio
async def test_scripted_llm_service_stream_reply_called_stays_false_if_never_invoked() -> None:
    service = ScriptedLLMService(
        plan_response='{"clarification_needed": "Which invoices - all, unpaid, or overdue?"}',
        response_text="",
    )
    await service.complete("system", [], "Show invoices")
    assert service.stream_reply_called is False


class _FakeRealService:
    def __init__(self, plan_response: str, tokens: list[str]) -> None:
        self._plan_response = plan_response
        self._tokens = tokens

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        return self._plan_response

    async def stream_reply(self, system: str, history: list[dict[str, str]], message: str):
        for token in self._tokens:
            yield token


@pytest.mark.asyncio
async def test_recording_llm_service_delegates_and_buffers() -> None:
    wrapped = _FakeRealService(
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        tokens=["Today ", "is ", "Tuesday."],
    )
    recorder = RecordingLLMService(wrapped)

    raw = await recorder.complete("system", [], "What's today?")
    assert raw == '{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}'
    assert recorder.last_plan_response == raw

    chunks = [chunk async for chunk in recorder.stream_reply("system", [], "What's today?")]
    assert chunks == ["Today ", "is ", "Tuesday."]
    assert recorder.last_response_text == "Today is Tuesday."
    assert recorder.stream_reply_called is True


@pytest.mark.asyncio
async def test_recording_llm_service_stream_reply_called_false_until_invoked() -> None:
    wrapped = _FakeRealService(plan_response='{"clarification_needed": "which?"}', tokens=[])
    recorder = RecordingLLMService(wrapped)
    await recorder.complete("system", [], "Show invoices")
    assert recorder.stream_reply_called is False
    assert recorder.last_response_text is None
