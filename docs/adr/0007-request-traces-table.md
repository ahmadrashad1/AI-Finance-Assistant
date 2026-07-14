# 0007 — Request Traces as Their Own Table

## Status

Accepted

## Context

Debugging AI behavior requires knowing, for every turn: which plan branch
fired, which prompt versions produced it, what was executed, and how long
it took. Tool executions were already logged (`application.tool_executions`),
but turns that produce no tool calls — clarifications, refusals, direct
answers — left no queryable record of the plan at all. Response-text
heuristics cannot distinguish a refusal from a clarification (refusals
skip Phase 2 entirely), which also blocked the evaluation framework from
scoring `expected_out_of_scope` reliably.

## Decision

`application.request_traces` is its own table, written on every turn by
`ChatWorkflow`: unique `request_id` (String(64)), conversation id, the
full plan as JSONB, both prompt versions, and `total_duration_ms` stamped
in a `finally` so even failed turns get a duration. It is exposed via
`GET /api/trace/{request_id}` (plan + prompt versions + duration + the
turn's tool executions) and rendered in the frontend behind a "View
trace" toggle on every assistant message, correlated through the
`x-request-id` response header.

## Alternatives Considered

- **Columns on `application.messages`.** Rejected: a trace exists even
  for turns whose persisted message shape doesn't change (refusals,
  clarifications, errors before a message is written), and the trace is
  observability data, not conversation content.
- **Structured logs only.** Rejected: logs are not queryable as ground
  truth by the eval runner or joinable to tool executions by request id;
  the eval framework needs to read the fired branch back per case.
- **Full tracing infrastructure (OpenTelemetry).** Rejected for the MVP:
  production observability is explicitly out of scope (PRD Chapter 6);
  one table covers the development need (NFR-16).

## Rationale

A dedicated table gives every turn — regardless of branch — one queryable
observability record, joins cleanly to `tool_executions` by `request_id`
(indexed), and serves as ground truth for both the evaluation framework
(`expected_out_of_scope` reads the fired branch from it) and the demo
evidence in `docs/DEMO.md` (`backend/scripts/run_demo.py` fetches each
turn's trace via the API).

## Consequences

- Every turn costs one extra insert plus a finalizing update; acceptable
  at MVP scale and indexed for the trace API's join.
- `request_id` is `String(64)`, which constrains evaluation case ids to
  ≤44 characters (eval ids expand to `eval-{id}-{8-char token}-turnN`).
- The trace panel is developer tooling: it exposes the raw
  `error_message` (not the user-facing friendly text) by design —
  developers get the detailed, categorized error; users get the friendly
  message (CLAUDE.md).
