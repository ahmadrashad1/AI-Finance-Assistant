# Evaluation Framework

Implements Evaluation-Driven Development (EDD): every AI capability ships
with automated evaluation cases (prompt, expected tool, expected parameters,
expected response quality) that are run and scored on every change.

Tracks tool-selection accuracy, parameter-extraction accuracy, groundedness,
hallucination rate, and conversation-memory correctness over time so
regressions are caught before merge, not in production.
