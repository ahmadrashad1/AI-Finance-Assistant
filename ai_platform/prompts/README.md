# Prompts

Versioned prompt artifacts. Prompts are code: every content change bumps
`VERSION`, updates the module's changelog, and requires an eval-suite
re-run before merge (CLAUDE.md rule — a prompt change without re-run
evaluations is not mergeable).

- `planning_prompt.py` — the Phase-1 planner prompt: renders the tool
  registry, defines the four mutually exclusive plan branches
  (`tool_calls` / `clarification_needed` / `direct_answer` /
  `out_of_scope_refusal`), and the parameter-extraction rules.
- `system_prompt.py` — the Phase-2 response prompt: grounding rules (use
  only validated tool output), markdown-table formatting for list results,
  truncation acknowledgement, and explanation/citation requirements.

**Warning:** eval cassettes are keyed by the hash of both `VERSION`s
(`ai_platform/evaluation/cassette.py`), so bumping either stales every
recorded cassette and commits you to a full re-record (~450k tokens ≈ one
Groq free-tier day at the current 53 cases). Never bump casually; batch
prompt changes per milestone. See
`docs/adr/0005-cassette-record-replay-evaluation.md`.

This package is pure data + builder functions with no dependencies;
consumed by the planner, the chat workflow, and the evaluation framework.
