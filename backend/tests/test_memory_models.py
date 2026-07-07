from ai_platform.memory.models import ConversationModel, MessageModel, SessionModel


def test_models_use_application_schema() -> None:
    assert SessionModel.__table__.schema == "application"
    assert ConversationModel.__table__.schema == "application"
    assert MessageModel.__table__.schema == "application"


def test_conversation_references_session() -> None:
    fk_targets = {fk.target_fullname for fk in ConversationModel.__table__.foreign_keys}
    assert "application.sessions.id" in fk_targets


def test_message_references_conversation() -> None:
    fk_targets = {fk.target_fullname for fk in MessageModel.__table__.foreign_keys}
    assert "application.conversations.id" in fk_targets


def test_message_has_role_and_content_columns() -> None:
    columns = {c.name for c in MessageModel.__table__.columns}
    assert {"id", "conversation_id", "role", "content", "created_at"} <= columns
