from ai_platform.memory.conversation_memory import HistoryMessage
from ai_platform.orchestration.prompt_builder import PromptBuilder


def test_build_includes_system_prompt_verbatim() -> None:
    builder = PromptBuilder()
    result = builder.build("You are helpful.", [])
    assert result.system == "You are helpful."
    assert result.messages == []


def test_build_converts_history_to_role_content_dicts() -> None:
    builder = PromptBuilder()
    history = [
        HistoryMessage(role="user", content="Hello"),
        HistoryMessage(role="assistant", content="Hi there"),
    ]
    result = builder.build("system prompt", history)
    assert result.messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
