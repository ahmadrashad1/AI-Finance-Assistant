# 0001 — FastAPI as Orchestrator

## Status

Accepted

## Context

The AI Finance Assistant needs a component that owns the full request
lifecycle — receiving user messages, retrieving conversation memory,
calling the LLM, executing business tools, validating results, and
returning a response. Many AI applications let the LLM (or an agent
framework) call tools directly, with the application acting mostly as a
thin transport layer around the model.

We need to decide who is in control of execution: the LLM/agent framework,
or the application.

## Decision

FastAPI is the orchestrator for every request. It owns session management,
conversation memory, prompt construction, tool validation, tool execution,
result validation, logging, and response delivery. The LLM never accesses
PostgreSQL, never generates SQL, never knows table names, and never
executes Python directly — it only reasons over business concepts and
returns structured planning/response output that FastAPI validates before
acting on it.

## Alternatives Considered

- **LLM-direct tool-calling / agent frameworks**, where the model's
  function-calling loop drives execution with the framework as a thin
  wrapper. Rejected: makes it harder to validate inputs/outputs before
  execution, harder to guarantee deterministic behavior, and couples
  business logic to the model provider's tool-calling semantics.
- **Text-to-SQL**, where the LLM generates SQL against the finance schema
  directly. Rejected outright — this is explicitly forbidden by the
  project's core philosophy (Principle 1: AI is the decision maker, not
  the database).
- **Frontend-orchestrated execution**, where the Next.js app calls tools
  or the LLM directly and assembles the response. Rejected: violates
  separation of responsibilities (Principle 12) and would leak business
  logic into the presentation layer.

## Rationale

Keeping FastAPI in control at every step means every tool call can be
validated before execution and every result validated before it reaches
the model, tool selection and parameters are inspectable and testable
independent of the LLM, the same orchestration logic can be reused across
domains (Finance today, HR/Procurement/Sales later), and swapping LLM
providers or the underlying data store never requires changing how
requests are controlled.

## Consequences

- More backend engineering upfront: every business capability must be
  implemented as an explicit, registered tool before the assistant can use
  it — there is no generic fallback.
- The orchestration layer (platform/orchestration, platform/workflow)
  becomes a first-class, heavily tested component, not an implementation
  detail of a single endpoint.
- Latency includes explicit validation steps (parameter validation, result
  validation) in addition to LLM calls; this is treated as an acceptable
  cost for determinism and explainability during MVP development
  (Chapter 5, NFR-10 sets localhost-appropriate performance goals, not
  production SLAs).
