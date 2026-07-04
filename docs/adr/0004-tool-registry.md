# 0004 — Tool Registry

## Status

Accepted

## Context

The LLM planner needs to know what business capabilities are available
(e.g. `get_unpaid_invoices`, `find_duplicate_invoice`) without ever seeing
implementation details — SQL, table names, repositories, or ORM models
(Principle 1, Principle 2). As the platform grows to support multiple
domains (Finance, then HR, Procurement, Sales), the number of tools and
the risk of inconsistent metadata or accidental exposure of unfinished
functions grows too.

## Decision

FastAPI maintains a central Tool Registry. Every tool registers explicit
metadata — name, description, required/optional parameters, return
schema, version, and owning domain — and the LLM planner reads only this
registry, never the codebase or raw Python functions directly.

## Alternatives Considered

- **Automatic reflection/discovery** of all functions in the codebase
  exposed as tools. Rejected: would expose partially-built or internal
  helper functions to the planner with no metadata contract, and any
  refactor could silently change what the LLM can call.
- **Free-form internal API access**, where the LLM can call arbitrary
  internal endpoints. Rejected outright — violates Principle 2 (every
  business operation is an explicit, deliberately designed tool) and
  removes the ability to validate calls before execution.
- **Tool list hardcoded only in the prompt text**, with no structured
  registry or runtime validation. Rejected: no single source of truth for
  parameter schemas, no versioning, and no way to validate planner output
  against a schema before execution.

## Rationale

A registry gives the planner a stable, curated view of business
capabilities that doesn't change when the backend is refactored (Chapter
9, Rule 9 — the LLM never sees internal layers), lets FastAPI validate
planner output (tool name, parameters) against a known schema before any
execution occurs, supports the deliberately small, high-value initial tool
set (Chapter 10 recommends ~20–30 tools rather than exposing everything),
and gives the platform a consistent mechanism for onboarding future
domains (HR, Procurement, Sales) without inventing a new discovery
mechanism each time.

## Consequences

- Every new tool requires an explicit registration step with full
  metadata before the planner can use it — there is no automatic exposure
  shortcut.
- Tool contracts are treated as versioned APIs: breaking changes require a
  new version, deprecation of the old one, and updated evaluations before
  the old version is removed (Chapter 9, Versioning).
- The registry becomes a required dependency at startup (Chapter 14,
  Startup Process — tools are registered before the application accepts
  requests), so a missing or malformed tool definition should fail fast
  rather than surface as a runtime planner error.
