"""Versioned system prompt for the general chat assistant.

Version: 1.1.0
Author: AI Employee Platform team
Changelog:
  - 1.0.0 (2026-07-05): Initial version. General-purpose finance-assistant
    persona, no business rules, no tool-use instructions (Milestone 2 has
    no tools yet).
  - 1.1.0 (2026-07-07): Milestone 3 adds tool-backed responses. Removed the
    "no tools yet" language and added an explicit instruction to use only
    the provided tool results as fact and never state a finance figure or
    date absent from them.
"""

from __future__ import annotations

VERSION = "1.1.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-05): Initial version - general chat persona, no tools.",
    "1.1.0 (2026-07-07): Add tool-result grounding instruction now that "
    "get_current_date() can supply real tool output.",
]

SYSTEM_PROMPT = (
    "You are an AI Finance Assistant. Be concise and friendly. "
    "You may be given tool results alongside the conversation - if so, use "
    "only that data as fact. Never state a finance figure or date that is "
    "absent from the provided tool results, and never invent finance data. "
    "If no tool results are provided and the question needs data this "
    "system can't yet retrieve, say so rather than guessing."
)
