from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Machine-readable record of every planted anomaly, generated at seed time
# (PRD Ch.19). Evaluation cases READ this file; expected values must never be
# hardcoded into eval cases. All identifiers are business codes (claim
# numbers, invoice numbers, asset tags...), never UUIDs, so the file is
# byte-identical across reseeds of the same seed.
DEFAULT_EXPECTATIONS_PATH = Path(__file__).resolve().parent / "expectations.json"


def write_expectations(
    expectations: dict[str, Any], path: Path = DEFAULT_EXPECTATIONS_PATH
) -> Path:
    path.write_text(
        json.dumps(expectations, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def load_expectations(path: Path = DEFAULT_EXPECTATIONS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
