from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ai_platform.evaluation.cassette import (
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
