from __future__ import annotations

import pytest
from pydantic import BaseModel

from ai_platform.tool_registry.registry import (
    DuplicateToolError,
    ToolContext,
    ToolRegistry,
    ToolSpec,
)


class _Params(BaseModel):
    value: int = 0


class _Result(BaseModel):
    doubled: int


async def _handler(params: _Params, context: ToolContext) -> _Result:
    return _Result(doubled=params.value * 2)


def _make_spec(name: str = "double_it") -> ToolSpec:
    return ToolSpec(
        name=name,
        description="Doubles a number.",
        parameters_model=_Params,
        result_model=_Result,
        handler=_handler,
    )


def test_register_and_get() -> None:
    registry = ToolRegistry()
    spec = _make_spec()
    registry.register(spec)
    assert registry.get("double_it") is spec
    assert registry.get("missing") is None


def test_register_rejects_duplicate_name() -> None:
    registry = ToolRegistry()
    registry.register(_make_spec())
    with pytest.raises(DuplicateToolError):
        registry.register(_make_spec())


def test_list_specs_returns_all_registered_tools() -> None:
    registry = ToolRegistry()
    registry.register(_make_spec("double_it"))
    registry.register(_make_spec("triple_it"))
    names = {spec.name for spec in registry.list_specs()}
    assert names == {"double_it", "triple_it"}


def test_to_planner_json_exposes_name_description_parameters_only() -> None:
    registry = ToolRegistry()
    registry.register(_make_spec())
    [spec_json] = registry.to_planner_json()
    assert spec_json["name"] == "double_it"
    assert spec_json["description"] == "Doubles a number."
    assert "properties" in spec_json["parameters"]
    assert "value" in spec_json["parameters"]["properties"]
    assert set(spec_json.keys()) == {"name", "description", "parameters"}
