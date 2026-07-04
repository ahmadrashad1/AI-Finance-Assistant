# Platform

Reusable, domain-agnostic AI employee infrastructure. Nothing here knows about
finance, invoices, or any specific business domain — that belongs under
`domains/`.

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
  "send the whole transcript").

A new domain (HR, procurement, sales, ...) should be able to plug into this
platform by adding tools and services under `domains/`, without changing
anything here.
