# Orchestration Engine

Owns the AI request lifecycle end to end. FastAPI endpoints delegate here;
this package never contains SQL, prompt-templating shortcuts, or business
rules.

Lifecycle: request context → memory retrieval → prompt build → planning LLM
call (Phase 1) → execution plan → parameter validation → tool execution →
result validation → response LLM call (Phase 2) → memory write → evaluation
hook → structured logging.

See `docs/adr/0001-fastapi-as-orchestrator.md` and
`docs/adr/0002-two-phase-llm-execution.md`.
