# 0002 — Two-Phase LLM Execution

## Status

Accepted

## Context

Most conversational AI applications make a single LLM call per turn: the
model reasons, decides on any tool calls, and drafts the user-facing reply
in one pass, often before tool results are fully verified. This makes it
easy for the model to blend fact (tool output) with unverified guesses in
the same response, which is unacceptable for a finance assistant where
hallucinations are treated as bugs (Principle 10).

## Decision

Every request is split into two logically distinct LLM calls:

- **Phase 1 — Planning.** The model receives the user message, relevant
  conversation memory, and the tool registry. It decides user intent,
  whether clarification is required, which tool(s) to call, and what
  parameters to use. It produces no user-facing text in this phase.
- **Phase 2 — Response Generation.** After FastAPI has executed and
  validated the tool(s), the model receives only the original question
  plus verified, structured tool output, and generates the final natural-
  language response. No additional tool calls happen in this phase.

## Alternatives Considered

- **Single combined call** (plan + respond together). Rejected: the model
  can produce plausible-sounding prose before results are verified,
  making hallucinations harder to detect and attribute to a specific
  phase.
- **ReAct-style interleaved loop**, where the model freely alternates
  between reasoning, tool calls, and partial responses until it decides
  it's done. Rejected for the MVP: harder to bound, harder to log/evaluate
  deterministically, and gives the model more implicit control over
  execution than Principle 5 (Reason Before Acting, with no shortcuts)
  allows.

## Rationale

Separating planning from explanation means the response phase can only
speak about data that FastAPI has already fetched and validated, which
directly reduces hallucination risk (NFR-7). It also gives the evaluation
framework two independent, measurable stages — tool selection / parameter
extraction accuracy (Phase 1) and groundedness / explanation quality
(Phase 2) — rather than one blended metric (Chapter 8, AI Evaluation
Metrics).

## Consequences

- Each request costs at least two LLM round trips instead of one, adding
  latency; this is accepted under the localhost-first performance goals
  (NFR-10).
- Two separate prompt templates must be designed, versioned, and evaluated
  independently (Prompt Versioning standard, Chapter 17).
- The execution plan produced by Phase 1 must be validated and turned into
  a concrete tool-execution graph by FastAPI before Phase 2 ever runs —
  the planner cannot bypass validation to "just answer."
