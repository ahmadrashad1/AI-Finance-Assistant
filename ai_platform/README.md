# AI Platform

Reusable, domain-agnostic AI employee infrastructure. Nothing here knows
about finance, invoices, or any specific business domain — that belongs
under `domains/`. Importable as the `ai_platform` Python package; installed
editable into the backend's virtualenv (see `backend/README.md`).

- `orchestration/` — the AI request lifecycle: memory retrieval, prompt
  construction, planning, execution-plan building, tool dispatch, response
  generation, logging, and evaluation hooks. Implements the two-phase
  planning/response pattern (see `docs/adr/0002-two-phase-llm-execution.md`).
- `workflow/` — the workflow framework/SDK. Every workflow implements the same
  lifecycle: Initialize → Validate → Execute → Log → Evaluate → Complete.
- `tool_registry/` — registers and describes deterministic tools (name,
  description, parameters, return schema, version, domain) for the planner.
  The LLM only ever sees this registry, never raw code.
- `evaluation/` — the Evaluation-Driven Development (EDD) framework: eval
  case definitions, runs, scoring, and regression tracking.
- `memory/` — conversation memory management (selective retrieval, not
  "send the whole transcript"): sessions, conversations, messages, per-turn
  tool summaries, and request traces.
- `llm/` — the provider-agnostic `LLMService` protocol and its Groq /
  Anthropic implementations. Nothing else in the platform knows which
  provider is configured.
- `prompts/` — versioned prompt artifacts (planning prompt, system prompt).
  Every content change bumps `VERSION` and requires an eval-suite re-run
  before merge; eval cassettes are keyed by the hash of both versions.

A new domain (HR, procurement, sales, ...) should be able to plug into this
platform by adding tools and services under `domains/`, without changing
anything here.
