from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
