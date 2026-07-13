from __future__ import annotations

from pathlib import Path

import yaml

from ai_platform.evaluation.case_schema import EvalCase

DEFAULT_EVALS_ROOT = Path(__file__).resolve().parents[2] / "evals"


def load_suite(suite: str, *, evals_root: Path | None = None) -> list[EvalCase]:
    root = evals_root if evals_root is not None else DEFAULT_EVALS_ROOT
    suite_dir = root / suite
    if not suite_dir.is_dir():
        raise FileNotFoundError(f"No such eval suite directory: {suite_dir}")

    cases: list[EvalCase] = []
    for path in sorted(suite_dir.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        cases.append(EvalCase.model_validate(raw))

    if not cases:
        raise ValueError(f"Eval suite '{suite}' has no case files under {suite_dir}")
    return cases
