from __future__ import annotations

from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.tool_registry.executor import ToolExecutionOutcome


def _success_outcome(tool: str, result: dict[str, object]) -> ToolExecutionOutcome:
    return ToolExecutionOutcome(
        tool=tool, parameters={}, result=result, status="success",
        error_message=None, duration_ms=1,
    )


def _error_outcome(tool: str) -> ToolExecutionOutcome:
    return ToolExecutionOutcome(
        tool=tool, parameters={}, result=None, status="error",
        error_message="boom", duration_ms=1,
    )


def test_resolve_parameters_passes_through_literal_values_unchanged() -> None:
    planner = ExecutionPlanner()
    resolved, error = planner.resolve_parameters({"minimum_days": 30, "status": "overdue"}, [])
    assert error is None
    assert resolved == {"minimum_days": 30, "status": "overdue"}


def test_resolve_parameters_substitutes_a_step_reference() -> None:
    planner = ExecutionPlanner()
    prior = [_success_outcome("get_customer", {"customer_code": "CUST-0042"})]

    resolved, error = planner.resolve_parameters({"customer_id": "$step0.customer_code"}, prior)

    assert error is None
    assert resolved == {"customer_id": "CUST-0042"}


def test_resolve_parameters_mixes_literal_and_referenced_values() -> None:
    planner = ExecutionPlanner()
    prior = [_success_outcome("get_customer", {"customer_code": "CUST-0042"})]

    resolved, error = planner.resolve_parameters(
        {"customer_id": "$step0.customer_code", "minimum_days": 30}, prior
    )

    assert error is None
    assert resolved == {"customer_id": "CUST-0042", "minimum_days": 30}


def test_resolve_parameters_fails_when_step_index_does_not_exist() -> None:
    planner = ExecutionPlanner()
    resolved, error = planner.resolve_parameters({"customer_id": "$step0.customer_code"}, [])
    assert resolved is None
    assert error is not None
    assert "step 0" in error


def test_resolve_parameters_fails_when_referenced_step_did_not_succeed() -> None:
    planner = ExecutionPlanner()
    prior = [_error_outcome("get_customer")]

    resolved, error = planner.resolve_parameters({"customer_id": "$step0.customer_code"}, prior)

    assert resolved is None
    assert error is not None
    assert "did not succeed" in error


def test_resolve_parameters_fails_when_field_is_missing_from_the_result() -> None:
    planner = ExecutionPlanner()
    prior = [_success_outcome("get_customer", {"customer_name": "ABC Industries"})]

    resolved, error = planner.resolve_parameters({"customer_id": "$step0.customer_code"}, prior)

    assert resolved is None
    assert error is not None
    assert "customer_code" in error


def test_resolve_parameters_ignores_strings_that_are_not_step_references() -> None:
    planner = ExecutionPlanner()
    resolved, error = planner.resolve_parameters({"vendor_name": "$100 Traders"}, [])
    assert error is None
    assert resolved == {"vendor_name": "$100 Traders"}
