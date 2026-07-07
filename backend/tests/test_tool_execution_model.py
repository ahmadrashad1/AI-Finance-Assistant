from ai_platform.tool_registry.models import ToolExecutionModel


def test_model_uses_application_schema() -> None:
    assert ToolExecutionModel.__table__.schema == "application"


def test_references_conversation() -> None:
    fk_targets = {fk.target_fullname for fk in ToolExecutionModel.__table__.foreign_keys}
    assert "application.conversations.id" in fk_targets


def test_has_expected_columns() -> None:
    columns = {c.name for c in ToolExecutionModel.__table__.columns}
    assert {
        "id",
        "request_id",
        "conversation_id",
        "tool",
        "parameters",
        "result",
        "duration_ms",
        "status",
        "error_message",
        "created_at",
    } <= columns
