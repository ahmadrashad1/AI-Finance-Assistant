from __future__ import annotations

from dataclasses import dataclass

from ai_platform.memory.conversation_memory import HistoryMessage


@dataclass
class BuiltPrompt:
    system: str
    messages: list[dict[str, str]]


class PromptBuilder:
    """Assembles the system prompt + conversation memory + new user message
    into the shape an LLMService expects. Pure logic, no I/O.
    """

    def build(self, system_prompt: str, history: list[HistoryMessage]) -> BuiltPrompt:
        return BuiltPrompt(
            system=system_prompt,
            messages=[{"role": h.role, "content": h.content} for h in history],
        )
