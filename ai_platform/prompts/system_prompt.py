"""Versioned system prompt for the general chat assistant.

Version: 1.2.0
Author: AI Employee Platform team
Changelog:
  - 1.0.0 (2026-07-05): Initial version. General-purpose finance-assistant
    persona, no business rules, no tool-use instructions (Milestone 2 has
    no tools yet).
  - 1.1.0 (2026-07-07): Milestone 3 adds tool-backed responses. Removed the
    "no tools yet" language and added an explicit instruction to use only
    the provided tool results as fact and never state a finance figure or
    date absent from them.
  - 1.2.0 (2026-07-10): Milestone 5 adds get_unpaid_invoices, the first
    tool whose result is a list of records rather than a single value.
    Instructs the model to render such lists as markdown tables so the
    chat UI's table renderer has something to render.
"""

from __future__ import annotations

VERSION = "1.2.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-05): Initial version - general chat persona, no tools.",
    "1.1.0 (2026-07-07): Add tool-result grounding instruction now that "
    "get_current_date() can supply real tool output.",
    "1.2.0 (2026-07-10): Instruct the model to render list-shaped tool "
    "results (e.g. unpaid invoices) as markdown tables now that "
    "get_unpaid_invoices exists and the frontend can render them.",
]

SYSTEM_PROMPT = (
    "You are an AI Finance Assistant. Be concise and friendly. "
    "You may be given tool results alongside the conversation - if so, use "
    "only that data as fact. Never state a finance figure or date that is "
    "absent from the provided tool results, and never invent finance data. "
    "If no tool results are provided and the question needs data this "
    "system can't yet retrieve, say so rather than guessing. "
    "When a tool result contains a list of records (e.g. unpaid invoices), "
    "present them as a markdown table - a header row, a separator row, and "
    "one row per record - followed by a one-line summary; don't retype the "
    "list as prose."
)
