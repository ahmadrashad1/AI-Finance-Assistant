# 0006 — Out-of-Scope Refusal as a First-Class Plan Branch

## Status

Accepted

## Context

Users ask for things the assistant must not do: destructive actions
("delete all invoices"), actions outside its capabilities ("send an
email"), and non-finance smalltalk. These must be refused politely — but
CLAUDE.md forbids keyword matching anywhere, and the two-phase execution
model (ADR 0002) means that by the time Phase 2 generates a reply, tools
selected in Phase 1 have already executed. A refusal decided in Phase 2
would arrive after the damage-equivalent (unnecessary tool execution,
wasted plan) had already happened.

## Decision

`Plan.out_of_scope_refusal` is a fourth mutually exclusive plan branch,
alongside `tool_calls`, `clarification_needed`, and `direct_answer`. The
Phase-1 planner — the LLM, reasoning over intent — decides when a request
is out of scope and returns the refusal text in the plan. `ChatWorkflow`
early-returns it exactly like a clarification: no Phase 2 call, no tool
execution, and the fired branch is recorded in the request trace.

## Alternatives Considered

- **A keyword/pattern filter in front of the planner.** Rejected
  outright: violates the no-keyword-matching rule; "remove old invoices
  from the report" and "delete all invoices" differ by intent, not by
  vocabulary.
- **Refusing in Phase 2 via the system prompt.** Rejected: Phase 1 would
  still plan and execute tools for the refused request; the refusal
  would be a veneer over work that should never have happened.
- **A separate classifier model/call before planning.** Rejected for the
  MVP: adds latency and a second model dependency for something the
  planner already has full context to decide in the same call.

## Rationale

Making refusal a plan branch keeps intent understanding entirely the
LLM's job (the CLAUDE.md rule) while making refusals structurally unable
to execute tools — the branch is mutually exclusive with `tool_calls` by
schema, not by convention. It also makes refusal behavior measurable: the
eval framework's `expected_out_of_scope` expectation reads the fired
branch back from `request_traces` (ADR 0007) as ground truth.

## Consequences

- Refusal quality is a prompt-engineering concern with eval coverage
  (5 out-of-scope cases as of Milestone 9), not a code path to patch.
- Known limitation: the branch under-triggers on some action requests
  ("send an email" plans tools until the too-many-tools guard fires) —
  documented in `docs/MVP-REPORT.md`, queued as a planning-prompt
  candidate for the next version bump.
- Every future domain (HR, Procurement) inherits refusal behavior for
  free: it lives in the platform's plan schema, not in domain code.
