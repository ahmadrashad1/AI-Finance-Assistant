from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_platform.evaluation.loader import load_suite


def _write_case(directory: Path, filename: str, case_id: str, user_message: str) -> None:
    (directory / filename).write_text(
        yaml.safe_dump(
            {
                "id": case_id,
                "category": "test_category",
                "user_message": user_message,
                "expectations": {
                    "expected_tools": [{"tool": "get_current_date", "parameters": {}}]
                },
            }
        ),
        encoding="utf-8",
    )


def test_load_suite_reads_every_yaml_file_sorted_by_filename(tmp_path: Path) -> None:
    suite_dir = tmp_path / "core"
    suite_dir.mkdir()
    _write_case(suite_dir, "b_case.yaml", "case-b", "second")
    _write_case(suite_dir, "a_case.yaml", "case-a", "first")

    cases = load_suite("core", evals_root=tmp_path)

    assert [c.id for c in cases] == ["case-a", "case-b"]


def test_load_suite_raises_for_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="core"):
        load_suite("core", evals_root=tmp_path)


def test_load_suite_raises_for_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "core").mkdir()
    with pytest.raises(ValueError, match="no case files"):
        load_suite("core", evals_root=tmp_path)
