# CLAUDE.md

This repository is the **AI Employee Platform**. Finance is the first
domain built on it (see `docs/PRD.md` for the full product/design spec and
`docs/adr/` for the reasoning behind the core architectural decisions).

The rules below are **non-negotiable**. If a change conflicts with them, the
rule wins — redesign the change, don't bend the rule. They apply to every
domain (Finance today, HR/Procurement/Sales later), not just Finance.

## Data access

- The LLM never accesses PostgreSQL, never generates SQL, and never knows
  table names or table relationships. It thinks only in business concepts
  (e.g. "unpaid invoices"), never in schema terms.
- Every business capability is a deterministic Python tool that returns
  structured JSON — never prose, never raw SQL results shaped ad hoc.

## Natural language, not keywords

- No keyword matching anywhere in the application. Intent understanding is
  the LLM's job; different phrasings of the same request must route to the
  same tool call.

## Two-phase LLM execution

- **Phase 1 (Planning):** the model selects tools and extracts parameters.
  It produces no user-facing text.
- **Phase 2 (Response generation):** the model generates the reply, but
  only over already-executed, already-validated tool output.
- See `docs/adr/0002-two-phase-llm-execution.md`.

## Orchestration

- FastAPI orchestrates every request end to end. The LLM reasons; it does
  not execute code, call the database, or run tools itself.
  See `docs/adr/0001-fastapi-as-orchestrator.md`.
- Layering is one-directional and strict:

      endpoints (thin) -> workflows -> services -> repositories -> PostgreSQL

  Endpoints contain no SQL, no business rules, no prompt construction, and
  no tool selection — they only receive requests, delegate to a workflow,
  and return a typed response.
- Tools never execute SQL directly, never generate user-facing prose, and
  never hold conversation or application state.

## Workflow lifecycle

- Every workflow follows the same lifecycle, with no steps skipped:

      Initialize -> Validate -> Execute -> Log -> Evaluate -> Complete

## Logging and errors

- Structured logging only — every log entry carries at minimum:
  timestamp, request_id, conversation_id, workflow, severity, component.
  No free-form, hard-to-search log messages.
- Every error is categorized as one of: **Validation | Business |
  Infrastructure | AI | Unexpected**. Users get a friendly message;
  developers get the detailed, categorized log.

## Testing and evaluation

- Every feature ships with unit tests, integration tests, **and** AI
  evaluation cases. A feature without all three is incomplete.
- Prompts are versioned artifacts: version, author, changelog, and
  evaluation results travel with every prompt change. A prompt change
  without a re-run of its evaluation suite is not mergeable.

## Naming

- Names reflect business meaning: `InvoiceService`, `CustomerRepository`,
  `GenerateAgingReportWorkflow`. Never `Manager`, `Helper`, `Utils`, or
  `Processor`.

## Always demonstrable

- The application must always be demonstrable end to end at every point in
  development. Never leave it in a half-built state — a smaller working
  slice beats a larger broken one.

## Where the detail lives

- Full product/design rationale: `docs/PRD.md`
- Architecture decisions: `docs/adr/0001-fastapi-as-orchestrator.md`,
  `docs/adr/0002-two-phase-llm-execution.md`,
  `docs/adr/0003-finance-simulator-over-real-erp.md`,
  `docs/adr/0004-tool-registry.md`
