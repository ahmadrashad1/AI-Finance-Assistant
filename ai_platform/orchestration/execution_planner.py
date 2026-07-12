from __future__ import annotations

import re
from typing import Any

from ai_platform.tool_registry.executor import ToolExecutionOutcome

_STEP_REFERENCE = re.compile(r"^\$step(\d+)\.(\w+)$")


class ExecutionPlanner:
    """Resolves `$stepN.field` parameter references against prior tool
    outcomes in the same plan - the deterministic "how" behind the
    LLM's declarative "what" (CLAUDE.md: FastAPI decides how it happens).
    Pure and synchronous: it never calls a tool itself, so the caller
    (ChatWorkflow) keeps full control of per-step event streaming.
    """

    def resolve_parameters(
        self, parameters: dict[str, Any], prior_outcomes: list[ToolExecutionOutcome]
    ) -> tuple[dict[str, Any] | None, str | None]:
        resolved: dict[str, Any] = {}
        for key, value in parameters.items():
            if not isinstance(value, str):
                resolved[key] = value
                continue
            match = _STEP_REFERENCE.match(value)
            if match is None:
                resolved[key] = value
                continue

            step_index = int(match.group(1))
            field = match.group(2)

            if step_index >= len(prior_outcomes):
                return None, f"Could not resolve {value}: step {step_index} does not exist"

            step_outcome = prior_outcomes[step_index]
            if step_outcome.status != "success" or step_outcome.result is None:
                return None, f"Could not resolve {value}: step {step_index} did not succeed"

            if field not in step_outcome.result:
                return (
                    None,
                    f"Could not resolve {value}: field '{field}' not found in step "
                    f"{step_index}'s result",
                )

            resolved[key] = step_outcome.result[field]

        return resolved, None
