# Orchestration Engine

Owns the AI request lifecycle end to end. FastAPI endpoints delegate here;
this package never contains SQL, prompt-templating shortcuts, or business
rules.

Lifecycle: request context → memory retrieval → prompt build → planning LLM
call (Phase 1) → execution plan → parameter validation → tool execution →
result validation → response LLM call (Phase 2) → memory write → evaluation
hook → structured logging.

The Phase-1 plan has four mutually exclusive branches: `tool_calls`,
`clarification_needed`, `direct_answer`, and `out_of_scope_refusal`.
Clarifications and refusals early-return before Phase 2 — they structurally
cannot execute tools. Every turn (all branches) writes a request trace
(plan, prompt versions, duration) used by the trace API, the frontend's
"View trace" panel, and the eval framework as ground truth. Phase 2 receives
only validated tool output with friendly error text; raw error detail stays
in logs and traces.

See `docs/adr/0001-fastapi-as-orchestrator.md`,
`docs/adr/0002-two-phase-llm-execution.md`,
`docs/adr/0006-out-of-scope-refusal-as-plan-branch.md`, and
`docs/adr/0007-request-traces-table.md`.
