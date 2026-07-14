# Milestone 10 — MVP Completion Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the MVP by auditing the whole system against CLAUDE.md and the PRD, fixing violations found, proving every PRD success criterion with scripted demo conversations, and producing the final documentation set (README quickstart, per-component docs, new ADRs, `docs/DEMO.md`, `docs/MVP-REPORT.md`) so a new developer can clone → demo in under 10 minutes.

**Architecture:** This is an audit-and-documentation milestone, not a feature milestone. There is exactly one planned code change (friendly tool-error messages — a known CLAUDE.md violation documented in HANDOFF.md §5), plus whatever the architecture-audit grep sweep surfaces. Everything else is verification runs, a demo-driver script, and documents. No prompt `VERSION` bump anywhere in this milestone — a bump stales all 53 cassettes and costs a full Groq free-tier day to re-record.

**Tech Stack:** Existing stack only — FastAPI backend (`backend/`), platform layer (`ai_platform/`), finance domain (`domains/finance/`), Next.js frontend (`frontend/`), Postgres 16 via docker compose, Groq `llama-3.1-8b-instant`, pytest / ruff / mypy strict, eval runner `python -m ai_platform.evaluation.run`. New script uses `httpx` (already a backend dev dependency via the test client).

## Global Constraints

Copied from CLAUDE.md and HANDOFF.md §6 — every task implicitly includes these:

- The LLM never accesses PostgreSQL, never generates SQL, never knows table names. No keyword matching anywhere. Two-phase execution (Plan, then Respond over validated output). Layering: endpoints → workflows → services → repositories → PostgreSQL, one-directional.
- **Do NOT bump `ai_platform/prompts/planning_prompt.py` or `system_prompt.py` `VERSION`** — every cassette goes stale by design; a bump commits you to a full ~450k-token re-record. If an audit fix seems to require a prompt change, STOP and surface it to your human partner instead.
- **Do NOT loosen eval expectations to force a green suite.** The 14 documented failing cases (39/53 in `--mode recorded`) are the framework's product. The eval baseline for this milestone is exactly **39/53, tool-selection 76.7%, parameter accuracy 94.4%, hallucination 0.0%**. Any deviation from that baseline is a regression to investigate, not a number to accept.
- **Do NOT run pytest (or anything using `clean_db`) between reseeding and any run that reads seeded finance data** (demo runs, SQL cross-checks) — pytest truncates the finance tables. Reseed with `python -m domains.finance.simulator.seed --reset` afterwards instead.
- **Do NOT run two recording processes concurrently**; verify no stray Python children with `tasklist | findstr python` before any `--record` work. (No recording is planned in this milestone; this applies only if a re-record becomes unavoidable.)
- Keep eval case ids ≤ 44 chars (not expected to add cases this milestone).
- **Do NOT push to `origin` without being asked.** Don't assume Docker Desktop is running — check first.
- All backend commands run from `backend/` using the project venv: `.venv/Scripts/python` (Windows). Structured logging and the five error categories (Validation | Business | Infrastructure | AI | Unexpected) apply to any code change.
- Names reflect business meaning — never `Manager`, `Helper`, `Utils`, `Processor`.
- Work on a feature branch `milestone-10-mvp-completion-audit` (same policy as Milestone 9).

## Verified starting state (2026-07-14)

- Milestone 9 is merged to `master` (HEAD `6c264f3`). 439 backend tests pass; ruff/mypy/frontend clean; eval suite 39/53 recorded.
- 12 tools registered. Prompts at planning 1.4.0 / system 1.5.0. Cassettes keyed by `case_id + turn + prompt-version hash` (`ai_platform/evaluation/cassette.py:20-22`) — **not** by request content, so code changes that alter Phase-2 input do NOT stale cassettes.
- Known CLAUDE.md violation (HANDOFF §5): Phase 2 quotes raw internal tool errors (e.g. `Tool 'get_customer' failed: ... $step0.customer_code ...`) to users. Leak paths: `ai_platform/orchestration/chat_workflow.py:46-58` (`_build_response_message` passes `outcome.error_message` verbatim into the Phase-2 prompt) and `chat_workflow.py:151-161` (resolution errors). Error strings originate in `ai_platform/tool_registry/executor.py:56,62,69,75`.
- Services signal business failures as `ValueError` with already-user-appropriate messages (e.g. `domains/finance/services/invoice_service.py:112` → `"Customer not found: {customer_id}"`).
- `README.md` is stale: says "Milestone 1", documents a `platform/` directory that is actually `ai_platform/`, omits seeding, the LLM key, migrations, the eval suite, and `evals/`.
- Existing component READMEs: `ai_platform/README.md` (+ `evaluation/`, `memory/`, `orchestration/`, `tool_registry/`, `workflow/` sub-READMEs), `domains/README.md`, `domains/finance/README.md`, `backend/README.md`, `frontend/README.md`. **Missing:** `ai_platform/llm/README.md`, `ai_platform/prompts/README.md`.
- Existing ADRs: 0001 FastAPI orchestrator, 0002 two-phase execution, 0003 simulator over ERP, 0004 tool registry. Undocumented significant decisions: cassette record/replay evaluation, out-of-scope refusal as a fourth plan branch, `request_traces` as its own table.
- `docs/DEMO.md` and `docs/MVP-REPORT.md` do not exist yet.
- Chat API: `POST http://localhost:8000/api/chat` with JSON `{"session_id", "message", "conversation_id"?}`, streams SSE lines `data: {"type": "token"|"tool_call"|"done"|"error", ...}`; response header `x-request-id`; `GET /api/trace/{request_id}` returns the plan branch, prompt versions, duration, and tool executions.
- PRD gaps already known (must be *documented*, not silently fixed): FR-9 invoice-to-PO matching tool not implemented (deliberately deferred, HANDOFF §7.3); tool-selection accuracy 76.7% vs the PRD NFR-5 target of >95%.

---

### Task 1: Branch + clean-slate baseline verification (Milestone item 1)

**Files:**
- No file changes expected. Fixes only if a check regresses from the Milestone 9 baseline.

**Interfaces:**
- Produces: a verified green baseline every later task builds on, and the freshest `evaluation.evaluation_runs` row that Task 7's scorecard reads.

- [ ] **Step 1: Create the feature branch**

```bash
cd "D:\New-Automation\AI-FinanceAssistant"
git checkout master
git checkout -b milestone-10-mvp-completion-audit
```

- [ ] **Step 2: Verify Docker/Postgres**

Run: `docker compose ps`
Expected: `ai-financeassistant-postgres-1 ... healthy ... 0.0.0.0:5432`. If Docker Desktop isn't running, start it and run `docker compose up -d`, then re-check.

- [ ] **Step 3: Reseed and integrity-check the simulator**

```bash
cd backend
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m domains.finance.simulator.consistency_check
```

Expected: `Seeded Northwind Manufacturing Ltd. (seed=42).` then `Consistency check passed: 0 violations.`

- [ ] **Step 4: Full backend test suite**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: **439 passed** (~60s). Note: this truncates finance tables — reseed before any later step that reads seed data.

- [ ] **Step 5: Lint + strict types, full project scope**

```bash
cd backend
.venv/Scripts/python -m ruff check . ../ai_platform ../domains
.venv/Scripts/python -m mypy app alembic ../ai_platform ../domains
```

Expected: `All checks passed!` and `Success: no issues found in 106 source files`.

- [ ] **Step 6: Frontend checks**

```bash
cd frontend
npm run lint && npm run typecheck && npm run build
```

Expected: all clean, build compiles successfully.

- [ ] **Step 7: Reseed again (pytest truncated finance tables), then run the eval suite in recorded mode**

```bash
cd backend
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m ai_platform.evaluation.run --suite core
```

Expected output (the runner exits 1 because 14 cases are documented findings — that exit code is expected and correct here):

```
Total: 39/53 passed
Tool-selection accuracy: 76.7%
Parameter accuracy: 94.4%
Memory usage accuracy: 0.0%
Hallucination rate: 0.0%
```

Also expected: **no `STALE` section** — a stale section means prompt files were touched; stop and investigate.

- [ ] **Step 8: Handle deviations (only if any step above deviated)**

If any check deviates from the Milestone 9 baseline, use the superpowers:systematic-debugging skill to find the root cause and fix it with TDD (failing test → fix → pass). Do not proceed to Task 2 with a regressed baseline. Commit any such fix separately:

```bash
git add <files>
git commit -m "fix: restore Milestone 9 baseline (<what regressed>)"
```

- [ ] **Step 9: Record the baseline numbers**

Copy the eval scorecard block and pytest/ruff/mypy summaries into a working notes file for Task 7:

Create `docs/superpowers/plans/2026-07-14-milestone-10-audit-findings.md` with:

```markdown
# Milestone 10 audit — working notes

## Baseline (Task 1, 2026-07-14)
- pytest: <N> passed
- ruff/mypy: clean (<N> files)
- frontend lint/typecheck/build: clean
- eval core recorded: 39/53 | tool-selection 76.7% | params 94.4% | memory 0.0% | hallucination 0.0%
- stale cassettes: none

## Architecture audit findings (Task 2)
(filled in by Task 2)
```

```bash
git add docs/superpowers/plans/2026-07-14-milestone-10-audit-findings.md
git commit -m "docs: start Milestone 10 audit working notes with verified baseline"
```

---

### Task 2: Architecture audit against CLAUDE.md (Milestone item 3)

**Files:**
- Modify: `docs/superpowers/plans/2026-07-14-milestone-10-audit-findings.md` (append findings)
- Modify: any file where a genuine violation is found (fix with TDD)

**Interfaces:**
- Consumes: green baseline from Task 1.
- Produces: a complete findings list (violation → file:line → resolution) that Task 7 folds into `docs/MVP-REPORT.md`'s "Architecture audit" section. The known Phase-2 error-leak violation is *recorded* here but *fixed* in Task 3.

Run every grep from the repo root (`D:\New-Automation\AI-FinanceAssistant`). For each hit, classify: **violation** (fix now, TDD), **judgment call** (document reasoning in the findings file), or **false positive** (note and move on). Zero hits is also a result — record "clean".

- [ ] **Step 1: SQL outside repositories**

```bash
grep -rn --include=*.py -E "select\(|text\(|insert\(|update\(|delete\(|\.execute\(|\.scalars?\(" \
  domains/finance/tools domains/finance/services domains/finance/simulator \
  ai_platform backend/app/api backend/app/middleware backend/app/main.py
```

Allowed locations (not searched or hits there are fine): `domains/finance/repositories/`, `backend/app/db/`, `backend/alembic/`, `ai_platform/*/repository.py`, `ai_platform/evaluation/repository.py`, tests. If the simulator seed/consistency-check uses the session directly, record it as a judgment call (the simulator *is* the ERP stand-in, below the repository boundary from the AI's perspective) rather than rewriting it — unless it embeds raw SQL strings, which would be a violation.

- [ ] **Step 2: Business logic or SQL in endpoints**

Endpoints must only receive → delegate → return. Read all three files fully (they are short):
`backend/app/api/chat.py`, `backend/app/api/trace.py`, `backend/app/api/health.py`.
Constructing the workflow's dependencies (as `post_chat` does) is DI wiring, not business logic — not a violation. Any filtering, calculation, prompt text, or tool selection in an endpoint IS a violation.

- [ ] **Step 3: Prose generated inside tools**

```bash
grep -rn --include=*.py -E "return \"|return f\"" domains/finance/tools
```

Tools must return Pydantic result models only. Also skim each tool module confirming the handler returns a model and contains no user-facing sentence construction.

- [ ] **Step 4: Keyword matching anywhere**

```bash
grep -rn --include=*.py -E "\.lower\(\)|\.upper\(\)|\.startswith\(|\.endswith\(|re\.(search|match|findall|compile)" \
  ai_platform domains backend/app
```

Violation = any branching on the *user's message content* outside the LLM (that's intent-by-keyword). NOT violations: case-insensitive *data* matching (e.g. ILIKE fragment search in `CustomerRepository.search_by_name`), log formatting, header parsing. Classify every hit explicitly in the findings file.

- [ ] **Step 5: Unversioned prompt edits**

```bash
git log --oneline --follow -- ai_platform/prompts/planning_prompt.py
git log --oneline --follow -- ai_platform/prompts/system_prompt.py
```

For each commit that changed prompt *content*, confirm the same commit bumped `VERSION` and changelog (inspect with `git show <sha> -- ai_platform/prompts/<file>`). Confirm current versions are exactly 1.4.0 (planning) and 1.5.0 (system) and match the latest `evaluation_runs` row from Task 1.

- [ ] **Step 6: Layering direction + naming**

```bash
# lower layers must never import upward; domains/ai_platform must not import the backend app
grep -rn --include=*.py -E "^from app|^import app|from backend" ai_platform domains
# endpoints reaching past workflows straight into services/repositories
grep -rn --include=*.py "from domains" backend/app/api
# banned names
grep -rniE --include=*.py "class \w*(Manager|Helper|Utils|Processor)\b" ai_platform domains backend/app
```

Expected: no upward imports; `backend/app/api` imports domains only for DI wiring types if at all (judgment call — document); no banned class names.

- [ ] **Step 7: Structured-logging and error-category spot check**

```bash
grep -rn --include=*.py -E "print\(" ai_platform domains backend/app
```

`print()` is fine in CLI entry points (`seed`, `consistency_check`, `evaluation/run.py`, profiling scripts) — a violation anywhere in request-path code.

- [ ] **Step 8: Record all findings**

Append to `docs/superpowers/plans/2026-07-14-milestone-10-audit-findings.md` a table:

```markdown
## Architecture audit findings (Task 2)
| # | Rule | Location | Classification | Resolution |
|---|------|----------|----------------|------------|
| 1 | Friendly errors (CLAUDE.md "Users get a friendly message") | ai_platform/orchestration/chat_workflow.py:46-58, 151-161; ai_platform/tool_registry/executor.py:56-75 | Violation (pre-known, HANDOFF §5) | Fixed in Task 3 |
| ... | | | | |
```

- [ ] **Step 9: Fix any *new* genuine violations found (TDD), then verify**

For each new violation: write a failing test in the matching `backend/tests/test_*.py` file, fix minimally, run the test, then run the full suite + lint + types (Task 1 Steps 4–5 commands). Then reseed and re-run the eval suite (Task 1 Step 7) and confirm the 39/53 baseline is unchanged.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "audit: architecture sweep against CLAUDE.md; record findings (fixes: <list or none>)"
```

---

### Task 3: Friendly tool-error messages (fixes the known CLAUDE.md violation)

**Files:**
- Modify: `ai_platform/tool_registry/executor.py`
- Modify: `ai_platform/orchestration/chat_workflow.py:46-58` and `:151-161`
- Test: `backend/tests/test_tool_executor.py`, `backend/tests/test_chat_workflow.py`

**Interfaces:**
- Consumes: `ToolExecutionOutcome` (dataclass in `executor.py:19-27`), `_build_response_message(message: str, outcomes: list[ToolExecutionOutcome]) -> str` (`chat_workflow.py:46`).
- Produces: `ToolExecutionOutcome` gains a final field `user_error_message: str | None = None`. `error_message` (raw, detailed) keeps flowing to logs, `tool_executions`, and traces — developers still get full detail per CLAUDE.md. Only the Phase-2 prompt switches to the friendly text.

Design: services already raise `ValueError` with user-appropriate business messages ("Customer not found: X") — pass those through. Everything else (Pydantic dumps, `$step0.*` resolution errors, unexpected exceptions, result-validation internals) gets a category-appropriate friendly sentence. No prompt changes; cassettes are keyed by prompt-version hash only, so recorded evals are unaffected.

- [ ] **Step 1: Write failing executor tests**

Append to `backend/tests/test_tool_executor.py`, following the file's existing fixture pattern (`clean_db`, `db_session`, `_make_conversation`, in-test `ToolRegistry` + `ToolSpec` — see `test_execute_records_success` at the top of the file):

```python
async def _not_found_handler(params: _OkParams, context: ToolContext) -> _OkResult:
    raise ValueError("Customer not found: Anchor")


@pytest.mark.asyncio
async def test_business_value_error_passes_through_as_user_message(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-friendly-1")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="get_customer",
            description="Fetch a customer.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_not_found_handler,
        )
    )
    executor = ToolExecutor(registry, ToolExecutionRepository(db_session), db_session)

    outcome = await executor.execute(
        request_id="req-f1", conversation_id=conversation_id,
        tool="get_customer", parameters={"value": 1},
    )

    assert outcome.status == "error"
    # business message passes through untouched; no internal framing
    assert outcome.user_error_message == "Customer not found: Anchor"
    # developer detail is preserved for logs/traces
    assert "get_customer" in (outcome.error_message or "")


@pytest.mark.asyncio
async def test_unexpected_exception_is_masked_in_user_message(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-friendly-2")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_crashing_handler,
        )
    )
    executor = ToolExecutor(registry, ToolExecutionRepository(db_session), db_session)

    outcome = await executor.execute(
        request_id="req-f2", conversation_id=conversation_id,
        tool="double_it", parameters={"value": 1},
    )

    assert outcome.status == "error"
    assert outcome.user_error_message is not None
    assert "boom" not in outcome.user_error_message
    assert "failed" not in outcome.user_error_message.lower() or "internal" in outcome.user_error_message.lower()
    assert "boom" in (outcome.error_message or "")  # developers keep the detail


@pytest.mark.asyncio
async def test_invalid_parameters_masked_in_user_message(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-friendly-3")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_ok_handler,
        )
    )
    executor = ToolExecutor(registry, ToolExecutionRepository(db_session), db_session)

    outcome = await executor.execute(
        request_id="req-f3", conversation_id=conversation_id,
        tool="double_it", parameters={"value": "$50,000"},
    )

    assert outcome.status == "error"
    assert outcome.user_error_message is not None
    # Pydantic internals must not reach the user
    assert "pydantic" not in outcome.user_error_message.lower()
    assert "validation error" not in outcome.user_error_message.lower()
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_tool_executor.py -q -k friendly or masked or passes_through`
(Adjust `-k` to match: `-k "user_message or masked"`.)
Expected: FAIL — `ToolExecutionOutcome` has no attribute `user_error_message`.

- [ ] **Step 3: Implement in the executor**

In `ai_platform/tool_registry/executor.py`, extend the dataclass (new field LAST, with a default, so the construction site in `chat_workflow.py` and any test fixtures keep working):

```python
@dataclass
class ToolExecutionOutcome:
    tool: str
    parameters: dict[str, Any]
    result: dict[str, Any] | None
    status: str
    error_message: str | None
    duration_ms: int
    user_error_message: str | None = None
```

Then set both messages at each error site in `execute()`:

```python
        spec = self._registry.get(tool)
        if spec is None:
            status = "error"
            error_message = f"Unknown tool: {tool}"
            user_error_message = "That capability isn't available."
        else:
            try:
                validated_params = spec.parameters_model.model_validate(parameters)
            except PydanticValidationError as exc:
                status = "error"
                error_message = f"Invalid parameters for tool '{tool}': {exc}"
                user_error_message = (
                    "One of the values in this request wasn't in a usable format."
                )
            else:
                try:
                    context = ToolContext(db=self._db)
                    raw_result = await spec.handler(validated_params, context)
                except ValueError as exc:
                    # Business errors carry user-appropriate messages by convention
                    status = "error"
                    error_message = f"Tool '{tool}' failed: {exc}"
                    user_error_message = str(exc)
                except Exception as exc:
                    status = "error"
                    error_message = f"Tool '{tool}' failed: {exc}"
                    user_error_message = "This lookup failed because of an internal error."
                else:
                    try:
                        result = validate_result(spec, raw_result.model_dump())
                    except ResultValidationError as exc:
                        status = "error"
                        error_message = str(exc)
                        user_error_message = (
                            "This lookup returned data that failed an internal check."
                        )
```

Initialize `user_error_message: str | None = None` alongside the existing locals at the top of `execute()`, and add it to the returned `ToolExecutionOutcome(...)`. Do NOT add it to `record_execution` — the DB row keeps the raw developer message only.

- [ ] **Step 4: Run the executor tests**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_tool_executor.py -q`
Expected: all pass, including the three new tests.

- [ ] **Step 5: Write failing workflow tests**

Append to `backend/tests/test_chat_workflow.py`, reusing that file's existing fakes/fixtures for the workflow (follow the pattern of its existing error-path test if one exists; otherwise its simplest passing test). Two assertions matter — test them at the seam that is easiest in that file, which is the module-level function `_build_response_message`:

```python
from ai_platform.orchestration.chat_workflow import _build_response_message
from ai_platform.tool_registry.executor import ToolExecutionOutcome


def test_build_response_message_uses_friendly_error() -> None:
    outcome = ToolExecutionOutcome(
        tool="get_customer",
        parameters={"customer_code": "$step0.customer_code"},
        result=None,
        status="error",
        error_message="Tool 'get_customer' failed: unresolved reference $step0.customer_code",
        duration_ms=3,
        user_error_message="Customer not found: Anchor",
    )
    message = _build_response_message("Show me Anchor's invoices", [outcome])
    assert "Customer not found: Anchor" in message
    assert "$step0" not in message
    assert "Tool 'get_customer' failed" not in message


def test_build_response_message_masks_missing_friendly_error() -> None:
    outcome = ToolExecutionOutcome(
        tool="get_customer",
        parameters={},
        result=None,
        status="error",
        error_message="RuntimeError: connection reset",
        duration_ms=3,
    )
    message = _build_response_message("Show me Anchor's invoices", [outcome])
    assert "connection reset" not in message
    assert "couldn't be completed" in message or "internal error" in message
```

- [ ] **Step 6: Run to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_workflow.py -q -k build_response_message`
Expected: FAIL — raw `error_message` still present in the built message.

- [ ] **Step 7: Implement in the workflow**

In `ai_platform/orchestration/chat_workflow.py`, change `_build_response_message` (line 46) to prefer the friendly message and never fall back to the raw one:

```python
def _build_response_message(message: str, outcomes: list[ToolExecutionOutcome]) -> str:
    if not outcomes:
        return message
    results = [
        {
            "tool": outcome.tool,
            "status": outcome.status,
            "result": cap_result_for_prompt(outcome.result),
            "error": (
                outcome.user_error_message
                or ("This step couldn't be completed because of an internal error." if outcome.error_message else None)
            ),
        }
        for outcome in outcomes
    ]
    return f"{message}\n\n[Tool results — use only this data]\n{json.dumps(results)}"
```

And at the resolution-error site (line ~151), add a friendly message to the synthesized outcome:

```python
                if resolution_error is not None:
                    outcomes.append(
                        ToolExecutionOutcome(
                            tool=tool_call.tool,
                            parameters=tool_call.parameters,
                            result=None,
                            status="error",
                            error_message=resolution_error,
                            duration_ms=0,
                            user_error_message=(
                                "An earlier step didn't return the information "
                                "this lookup needed."
                            ),
                        )
                    )
                    continue
```

- [ ] **Step 8: Run the full backend suite + lint + types**

```bash
cd backend
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check . ../ai_platform ../domains
.venv/Scripts/python -m mypy app alembic ../ai_platform ../domains
```

Expected: 439 + 5 new = **444 passed** (adjust if Task 2 added tests); ruff/mypy clean. If any *existing* test asserted the old raw-error behavior in Phase-2 input, read it and update the assertion to the friendly contract — that is a deliberate contract change, not expectation-loosening (eval expectations are untouched).

- [ ] **Step 9: Confirm the eval baseline is untouched**

```bash
cd backend
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m ai_platform.evaluation.run --suite core
```

Expected: exactly the Task 1 baseline (39/53, no STALE). Cassettes replay recorded LLM responses keyed by case+turn+prompt-hash, so this change cannot alter recorded results — any deviation means something else broke; stop and debug.

Note for the findings file: recorded Phase-2 *responses* for error-path cases were generated against the old raw error text; live behavior now differs (it's friendlier). Record this drift as a note — re-recording those few cases is optional post-MVP work, not required (expectations still score identically).

- [ ] **Step 10: Live spot-check (the exact HANDOFF §5 repro)**

Start the backend (`cd backend && .venv/Scripts/python -m uvicorn app.main:app` in a background shell), then:

```bash
curl -s -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo-friendly-errors", "message": "Show me Anchor'\''s invoices"}'
```

Expected: the streamed reply may still say the customer wasn't found (the planner's known fragment-name gap), but must NOT contain `$step0`, `Tool '`, or `failed:`. Paste the observed reply into the findings file. Stop the server.

- [ ] **Step 11: Commit**

```bash
git add ai_platform/tool_registry/executor.py ai_platform/orchestration/chat_workflow.py backend/tests/test_tool_executor.py backend/tests/test_chat_workflow.py docs/superpowers/plans/2026-07-14-milestone-10-audit-findings.md
git commit -m "fix: stop quoting raw internal tool errors to users; Phase 2 now receives friendly, categorized error text"
```

---

### Task 4: Scripted demo conversations + docs/DEMO.md (Milestone item 2)

**Files:**
- Create: `backend/scripts/run_demo.py`
- Create: `docs/DEMO.md`

**Interfaces:**
- Consumes: `POST /api/chat` (SSE) and `GET /api/trace/{request_id}` as described in "Verified starting state". Live Groq access (`GROQ_API_KEY` in `backend/.env`); each turn costs ~5–9k tokens, the full demo set is ~15 turns ≈ 100–150k tokens — comfortably inside the 500k/day free tier, but don't run it repeatedly in a loop.
- Produces: `docs/DEMO.md`, the PRD-success-criteria evidence document that Task 7's MVP-REPORT references, and a rerunnable script a new developer uses to reproduce the demos.

The demo conversations, one per PRD success criterion. Phrasings deliberately use full customer names (the fragment-name planner gap is a *documented limitation*, shown honestly in demo 4, not hidden):

| # | PRD criterion | Conversation script |
|---|---------------|---------------------|
| 1 | Understands natural English (varied phrasings) | Three separate one-turn conversations, all expected to plan `get_unpaid_invoices`: "Show unpaid invoices." / "Which customers haven't paid us?" / "Outstanding invoices?" |
| 2 | Multi-turn context retention | One conversation: "Show me invoices for Anchor Components" → "Only the ones above $5,000" → "What's their total balance?" |
| 3 | Correct tool selection + parameter extraction | One-turn each: "Show invoices overdue by more than 60 days" (`get_overdue_invoices`, `minimum_days=60`); "Generate an aging report" (`get_aging_report`); "Find duplicate invoices" (`find_duplicate_invoices`); "What's our cash position?" (`get_cash_position`) |
| 4 | Accurate data, zero hallucinated finance data | "Show me invoice INV-99999" (honest not-found); "Show me unpaid invoices over $10,000,000" (honest empty result); "Show me Anchor's invoices" (fragment-name gap: guardrails hold, honest not-found, no fabrication) |
| 5 | Clear explanations | "Generate an aging report and explain which bucket worries you most" (reply must cite real figures); "Delete all invoices" (out-of-scope refusal naming real capabilities) |

- [ ] **Step 1: Write the demo driver script**

Create `backend/scripts/run_demo.py`:

```python
"""Drive the PRD success-criterion demo conversations against a running backend.

Prerequisites (see README):
  * docker compose up -d ; database seeded with seed=42
  * backend running: uvicorn app.main:app (port 8000)
  * GROQ_API_KEY set in backend/.env

Usage:
    .venv/Scripts/python scripts/run_demo.py            # all demos
    .venv/Scripts/python scripts/run_demo.py --demo 2   # one demo

Prints a Markdown transcript (message, streamed reply, and the request
trace: plan branch, tools, parameters, duration) for docs/DEMO.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

import httpx

BASE_URL = "http://localhost:8000/api"

# Each demo: (title, PRD criterion, list of conversations, each a list of turns)
DEMOS: list[tuple[str, str, list[list[str]]]] = [
    (
        "Varied phrasings route to the same tool",
        "Understands natural English",
        [
            ["Show unpaid invoices."],
            ["Which customers haven't paid us?"],
            ["Outstanding invoices?"],
        ],
    ),
    (
        "Multi-turn context retention",
        "Holds multi-turn conversations and remembers context",
        [
            [
                "Show me invoices for Anchor Components",
                "Only the ones above $5,000",
                "What's their total balance?",
            ]
        ],
    ),
    (
        "Tool selection and parameter extraction",
        "Chooses the correct tools and extracts correct parameters",
        [
            ["Show invoices overdue by more than 60 days"],
            ["Generate an aging report"],
            ["Find duplicate invoices"],
            ["What's our cash position?"],
        ],
    ),
    (
        "Honesty under missing data",
        "Accurate data from the simulator; zero hallucinated finance data",
        [
            ["Show me invoice INV-99999"],
            ["Show me unpaid invoices over $10,000,000"],
            ["Show me Anchor's invoices"],
        ],
    ),
    (
        "Clear explanations and scope honesty",
        "Explains results clearly; refuses out-of-scope actions",
        [
            ["Generate an aging report and explain which bucket worries you most"],
            ["Delete all invoices"],
        ],
    ),
]


def run_turn(
    client: httpx.Client, session_id: str, conversation_id: str | None, message: str
) -> tuple[str, str | None, str | None]:
    """POST one chat turn. Returns (reply_text, conversation_id, request_id)."""
    reply_parts: list[str] = []
    new_conversation_id = conversation_id
    with client.stream(
        "POST",
        f"{BASE_URL}/chat",
        json={
            "session_id": session_id,
            "message": message,
            "conversation_id": conversation_id,
        },
        timeout=120.0,
    ) as response:
        response.raise_for_status()
        request_id = response.headers.get("x-request-id")
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: "):])
            if event["type"] == "token" and event.get("content"):
                reply_parts.append(event["content"])
            elif event["type"] == "done" and event.get("conversation_id"):
                new_conversation_id = event["conversation_id"]
            elif event["type"] == "error":
                reply_parts.append(f"[error event] {event.get('message')}")
    return "".join(reply_parts), new_conversation_id, request_id


def fetch_trace(client: httpx.Client, request_id: str) -> dict[str, object] | None:
    response = client.get(f"{BASE_URL}/trace/{request_id}")
    if response.status_code != 200:
        return None
    return response.json()


def print_trace(trace: dict[str, object] | None) -> None:
    if trace is None:
        print("> trace: unavailable")
        return
    print("> **Trace evidence:**")
    print("> ```json")
    for line in json.dumps(trace, indent=2, default=str).splitlines():
        print(f"> {line}")
    print("> ```")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=int, default=None, help="1-based demo number")
    args = parser.parse_args()

    selected = (
        [DEMOS[args.demo - 1]] if args.demo is not None else DEMOS
    )
    with httpx.Client() as client:
        for number, (title, criterion, conversations) in enumerate(selected, start=1):
            print(f"\n## Demo: {title}")
            print(f"*PRD criterion: {criterion}*\n")
            for conversation in conversations:
                session_id = f"demo-{uuid.uuid4().hex[:8]}"
                conversation_id: str | None = None
                for message in conversation:
                    print(f"**User:** {message}\n")
                    reply, conversation_id, request_id = run_turn(
                        client, session_id, conversation_id, message
                    )
                    print(f"**Assistant:** {reply}\n")
                    if request_id is not None:
                        print_trace(fetch_trace(client, request_id))
                    print()


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print(
            "Backend not reachable at http://localhost:8000 — start it with "
            "`uvicorn app.main:app` first.",
            file=sys.stderr,
        )
        sys.exit(1)
```

- [ ] **Step 2: Lint/type-check the script**

```bash
cd backend
.venv/Scripts/python -m ruff check scripts/run_demo.py
.venv/Scripts/python -m mypy scripts/run_demo.py
```

Expected: clean. (If mypy's configured file set excludes `scripts/`, add the path to the mypy invocation used in CI/Makefile or accept the standalone check — match whatever `backend/pyproject.toml` already does for other scripts; do not weaken any mypy settings.)

- [ ] **Step 3: Reseed, start the backend, run the demos live**

```bash
cd backend
.venv/Scripts/python -m domains.finance.simulator.seed --reset
# background shell:
.venv/Scripts/python -m uvicorn app.main:app
# then:
.venv/Scripts/python scripts/run_demo.py > ../docs/demo_transcript_raw.md
```

Expected: transcripts for all 5 demos. The planner is sampled at provider-default temperature, so a turn can occasionally misroute: re-run *that demo once* (`--demo N`) if a turn contradicts a criterion, and if it still misroutes, that phrasing is a genuine finding — keep the honest transcript and note it (as with the "Anchor" fragment case, which is *expected* to show the gap). Never edit a transcript to say something the assistant didn't say.

- [ ] **Step 4: Cross-check demo facts against the simulator via SQL**

For each factual claim in the transcripts (invoice numbers, amounts, bucket totals, cash position), verify against Postgres, e.g.:

```bash
docker compose exec postgres psql -U postgres -d finance_assistant -c \
  "SELECT invoice_number, total_amount, due_date FROM finance.invoices i \
   JOIN finance.customers c ON c.id = i.customer_id \
   WHERE c.company_name = 'Anchor Components' ORDER BY invoice_number;"
```

(Adapt db/user names to `docker-compose.yml` / `backend/.env`. Use `docker compose exec postgres psql -U <user> -l` to find the database name first.) Record each check as `claim → SQL → match/mismatch`. A mismatch is a hallucination — a bug; stop, file it via systematic-debugging, and do not paper over it.

- [ ] **Step 5: Write docs/DEMO.md**

Create `docs/DEMO.md` from the verified transcripts with this exact structure:

```markdown
# DEMO — PRD Success-Criteria Verification

Reproduce any demo yourself (takes <2 minutes once the app is running — see README):

    cd backend
    .venv/Scripts/python -m domains.finance.simulator.seed --reset
    .venv/Scripts/python scripts/run_demo.py

Dataset: Northwind Manufacturing Ltd., seed=42. Prompts: planning 1.4.0 / system 1.5.0.
Model: llama-3.1-8b-instant (Groq). The planner samples at provider-default temperature,
so replies vary in wording between runs; the tool selections below are the behavior the
evaluation suite pins (see docs/MVP-REPORT.md for the full scorecard and known gaps).

## Criterion 1 — Understands natural English (varied phrasings)
<transcript + trace evidence for the three phrasings, each showing plan branch
tool_calls -> get_unpaid_invoices>
**Verified:** all three phrasings, zero keyword matching (see MVP-REPORT audit), same tool.

## Criterion 2 — Multi-turn context retention
<transcript: the follow-ups resolve "the ones"/"their" from context; trace shows
parameters carrying the prior conversation's constraints>
**SQL cross-check:** <claim → query → result>

## Criterion 3 — Correct tool selection and parameter extraction
<four transcripts with trace evidence: tool name + extracted parameters each>

## Criterion 4 — Accurate data, zero hallucinated finance data
<three transcripts: honest not-found, honest empty result, and the documented
fragment-name gap ("Anchor") where guardrails hold and nothing is fabricated>

## Criterion 5 — Clear explanations (and scope honesty)
<aging-report explanation citing real figures + refusal transcript; trace of the
refusal shows the out_of_scope_refusal plan branch and zero tool executions>

## Summary
| PRD success criterion | Verdict | Evidence |
|---|---|---|
| Understands natural English | ✅ | Demo 1 |
| Multi-turn context retention | ✅ | Demo 2 |
| Correct tool selection & parameters | ✅ (with documented gaps) | Demo 3, MVP-REPORT §limitations |
| Accurate simulator data, zero hallucination | ✅ | Demo 4, eval hallucination rate 0.0% |
| Clear explanations | ✅ | Demo 5 |
```

Fill every `<...>` with the real, verified transcript content. Delete `docs/demo_transcript_raw.md` after DEMO.md is written.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/run_demo.py docs/DEMO.md
git commit -m "docs: add scripted demo conversations proving each PRD success criterion (docs/DEMO.md + backend/scripts/run_demo.py)"
```

---

### Task 5: README rewrite + per-component docs (Milestone item 4a/4b)

**Files:**
- Modify: `README.md` (root)
- Modify: `ai_platform/README.md`, `ai_platform/evaluation/README.md`, `ai_platform/memory/README.md`, `ai_platform/orchestration/README.md`, `ai_platform/tool_registry/README.md`, `ai_platform/workflow/README.md`, `domains/README.md`, `domains/finance/README.md`, `backend/README.md`, `frontend/README.md` (staleness pass)
- Create: `ai_platform/llm/README.md`, `ai_platform/prompts/README.md`

**Interfaces:**
- Consumes: the working demo script from Task 4 (README's demo step points at it).
- Produces: the `<10-minute` quickstart that Task 8 validates end-to-end on a fresh environment.

- [ ] **Step 1: Rewrite the root README's stale sections**

Keep the existing intro/philosophy sections (they're accurate); replace the **Repository layout**, **Getting started**, and **Status** sections. Repository layout must reflect reality (`ai_platform/` not `platform/`; add `evals/`, `docs/DEMO.md`, `docs/MVP-REPORT.md`). Getting started becomes:

```markdown
## Getting started (≈10 minutes)

Prerequisites: Docker Desktop (running), Python 3.13, Node 20+, a free
[Groq API key](https://console.groq.com).

```bash
# 1. Database (~1 min)
docker compose up -d

# 2. Backend (~4 min)
cd backend
python -m venv .venv && .venv/Scripts/activate   # source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env                             # then set GROQ_API_KEY=... in .env
alembic upgrade head                             # create the schema
python -m domains.finance.simulator.seed         # seed Northwind Manufacturing Ltd. (seed=42)
uvicorn app.main:app --reload                    # http://localhost:8000/api/health

# 3. Frontend (~3 min, new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev                                      # http://localhost:3000
```

Open http://localhost:3000 and ask: *“Which customers haven't paid us?”*,
*“Generate an aging report.”*, *“Find duplicate invoices.”*

## Demo, tests, and evaluation

```bash
cd backend
.venv/Scripts/python scripts/run_demo.py            # scripted PRD success-criterion demos (backend must be running)
.venv/Scripts/python -m pytest                      # unit + integration tests
.venv/Scripts/python -m ai_platform.evaluation.run --suite core   # AI evaluation suite (recorded mode, no API key needed)
```

The recorded eval suite deliberately reports 39/53 — the 14 failing cases are
documented model-behavior findings, not regressions. See `docs/MVP-REPORT.md`
for the scorecard and `docs/DEMO.md` for verified demo conversations.
```

Adjust the exact `alembic upgrade head` / seed invocation only if Task 8's fresh-environment run proves a different sequence is required — the README must match what actually works, verified, not what's assumed. Status section: MVP complete (Milestone 10); link `docs/DEMO.md`, `docs/MVP-REPORT.md`, `docs/adr/`.

- [ ] **Step 2: Staleness pass over the ten existing component READMEs**

Read each README listed above next to its package and correct factual drift only (don't rewrite style). Checklist per file — it must correctly state: purpose, responsibilities, dependencies (which layers it may import), and usage. Known drift to look for: tool count (now 12), the four `Plan` branches (`tool_calls` / `clarification_needed` / `direct_answer` / `out_of_scope_refusal`), request traces + `GET /api/trace/{request_id}`, eval suite size (53 cases) and `expected_out_of_scope`, prompt versions 1.4.0/1.5.0, the trace panel in the frontend.

- [ ] **Step 3: Write the two missing component READMEs**

Create `ai_platform/llm/README.md`:

```markdown
# ai_platform.llm

**Purpose:** Provider-agnostic LLM access. The rest of the platform depends only on
the `LLMService` interface — never on a concrete provider SDK.

**Responsibilities:**
- `LLMService` protocol: `complete()` (Phase-1 planning, returns the raw plan JSON)
  and `stream_reply()` (Phase-2 response generation, yields tokens).
- `GroqLLMService` and `AnthropicLLMService` implementations. Provider/model/key come
  from configuration (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`), never from code.

**Dependencies:** provider SDK clients only. Nothing in this package may import
orchestration, tools, domains, or the backend app.

**Usage:** constructed once per request in `backend/app/api/chat.py` (DI wiring) and
handed to the `Planner` and `ChatWorkflow`. The evaluation framework wraps it with
recording/replay services (`ai_platform/evaluation/cassette.py`).
```

Create `ai_platform/prompts/README.md`:

```markdown
# ai_platform.prompts

**Purpose:** Versioned prompt artifacts. Prompts are code: every content change bumps
`VERSION`, updates the changelog docstring, and requires an eval-suite re-run before merge
(CLAUDE.md rule).

**Contents:**
- `planning_prompt.py` (VERSION 1.4.0) — Phase-1 planner prompt: tool registry rendering,
  the four mutually exclusive plan branches, parameter-extraction rules.
- `system_prompt.py` (VERSION 1.5.0) — Phase-2 response prompt: grounding rules (use only
  validated tool output), explanation and citation requirements.

**Warning:** eval cassettes are keyed by the hash of both VERSIONs
(`ai_platform/evaluation/cassette.py`). Bumping either stales all 53 cassettes and
requires a full re-record (~450k tokens ≈ one Groq free-tier day). Never bump casually.

**Dependencies:** none (pure data + builder functions). Consumed by the planner,
workflow, and evaluation framework.
```

Verify the stated VERSIONs, class names, and function names against the actual source before committing — fix the README text, not the code, if they differ.

- [ ] **Step 4: Commit**

```bash
git add README.md ai_platform/llm/README.md ai_platform/prompts/README.md ai_platform/README.md ai_platform/*/README.md domains/README.md domains/finance/README.md backend/README.md frontend/README.md
git commit -m "docs: rewrite root README quickstart; refresh all component docs; add llm and prompts READMEs"
```

---

### Task 6: ADRs for undocumented significant decisions (Milestone item 4c)

**Files:**
- Create: `docs/adr/0005-cassette-record-replay-evaluation.md`
- Create: `docs/adr/0006-out-of-scope-refusal-as-plan-branch.md`
- Create: `docs/adr/0007-request-traces-table.md`

**Interfaces:**
- Consumes: decision rationale recorded in HANDOFF.md §4 and the Milestone 8/9 plans in `docs/superpowers/plans/`.
- Produces: ADRs referenced by Task 7's MVP-REPORT.

Match the format of the existing ADRs (read `docs/adr/0004-tool-registry.md` first and mirror its section headings — likely Status/Context/Decision/Consequences).

- [ ] **Step 1: Write ADR 0005 — cassette record/replay evaluation**

Content requirements (write in the existing ADR format, full prose):
- **Context:** the planner samples at provider-default temperature; live eval runs are nondeterministic, rate-limited (Groq 500k tokens/day sliding window), and slow. CI and the pre-merge eval gate need determinism.
- **Decision:** evaluations replay recorded LLM responses ("cassettes") keyed by `case_id + turn + prompt-version hash` (`ai_platform/evaluation/cassette.py`). `--record` re-writes cassettes from live calls; `--mode live` bypasses them. A prompt `VERSION` bump changes the hash, so every cassette reports STALE — a prompt change structurally cannot skip its eval re-run (the CLAUDE.md versioned-prompts rule, enforced by mechanism instead of discipline).
- **Consequences:** deterministic, free, offline eval runs; a 3-strike re-roll convention for declaring genuine model-behavior failures (a case fails only after 3+ independent recorded rolls fail); the cost is that a prompt bump commits to a full ~450k-token re-record, and recorded Phase-2 text can drift from current live behavior between re-records (e.g. the Task 3 friendly-error change).

- [ ] **Step 2: Write ADR 0006 — out-of-scope refusal as a first-class plan branch**

Content requirements:
- **Context:** requests like "delete all invoices" or "send an email" must be refused. A keyword filter would violate the no-keyword-matching rule; handling refusals in Phase 2 would let tools execute first.
- **Decision:** `Plan.out_of_scope_refusal` is a fourth mutually exclusive plan branch (alongside `tool_calls` / `clarification_needed` / `direct_answer`); `ChatWorkflow` early-returns it exactly like a clarification — no Phase 2, no tool execution. Intent understanding stays entirely the LLM's job; refusals structurally cannot execute tools.
- **Consequences:** refusal behavior is evaluable via the fired plan branch read back from `request_traces` (ground truth, not response-text heuristics); known limitation: the branch under-triggers on some action requests (documented in MVP-REPORT).

- [ ] **Step 3: Write ADR 0007 — request traces as their own table**

Content requirements:
- **Context:** debugging AI behavior needs the fired plan, prompt versions, and timing for *every* turn — including refusals and clarifications, which produce no tool executions and no distinctive message shape.
- **Decision:** `application.request_traces` is its own table (unique `request_id`, plan JSONB, both prompt versions, `total_duration_ms`), written on every turn and finished in a `finally`. Exposed via `GET /api/trace/{request_id}`, rendered in the frontend behind "View trace". The eval runner reads the fired branch from it as ground truth for `expected_out_of_scope`.
- **Consequences:** one queryable observability record per turn regardless of branch; the eval framework and the demo script (`backend/scripts/run_demo.py`) both use it as evidence; `request_id` is capped at `String(64)`, which constrains eval case-id length (≤44 chars).

- [ ] **Step 4: Verify cross-references and commit**

Confirm each mechanism described actually matches the code it cites (open the cited files; fix the ADR text if drifted).

```bash
git add docs/adr/0005-cassette-record-replay-evaluation.md docs/adr/0006-out-of-scope-refusal-as-plan-branch.md docs/adr/0007-request-traces-table.md
git commit -m "docs: add ADRs 0005-0007 (cassette evaluation, refusal plan branch, request traces)"
```

---

### Task 7: docs/MVP-REPORT.md (Milestone item 5)

**Files:**
- Create: `docs/MVP-REPORT.md`
- Delete: `docs/superpowers/plans/2026-07-14-milestone-10-audit-findings.md` (contents folded in)
- Delete: `backend/pytest_full.txt`, `backend/pytest_output.txt`, `backend/test_output.txt` (stray scratch files noted in HANDOFF; untracked — remove from disk)

**Interfaces:**
- Consumes: baseline + audit findings (Tasks 1–2), fix evidence (Task 3), DEMO.md (Task 4), ADRs (Task 6), and the latest `evaluation.evaluation_runs` row.
- Produces: the final MVP report the acceptance criteria call for.

- [ ] **Step 1: Pull the authoritative scorecard from the database**

```bash
docker compose exec postgres psql -U <user> -d <db> -c \
  "SELECT suite, mode, total_cases, passed_cases, planning_prompt_version, system_prompt_version, started_at \
   FROM evaluation.evaluation_runs ORDER BY started_at DESC LIMIT 3;"
```

(Column names: verify against `ai_platform/evaluation/models.py` first and adjust.) Use the most recent `core | recorded` row; it must match the Task 1/Task 3 runs (39/53, prompts 1.4.0/1.5.0).

- [ ] **Step 2: Check the FR-13 minimum-dataset criterion with SQL counts**

```bash
docker compose exec postgres psql -U <user> -d <db> -c \
  "SELECT 'customers' AS entity, count(*) FROM finance.customers \
   UNION ALL SELECT 'vendors', count(*) FROM finance.vendors \
   UNION ALL SELECT 'invoices', count(*) FROM finance.invoices \
   UNION ALL SELECT 'purchase_orders', count(*) FROM finance.purchase_orders \
   UNION ALL SELECT 'payments', count(*) FROM finance.payments;"
```

(Reseed first if pytest ran since the last seed. Adjust table names from `domains/finance/models/`.) PRD FR-13 minimums: 500 customers, 150 vendors, 10,000 invoices, 3,000 POs, 2,500 payments, 500 expense claims. Record actuals; any shortfall (expense claims likely don't exist as an entity) goes in Known Limitations — do not extend the simulator in this milestone.

- [ ] **Step 3: Write docs/MVP-REPORT.md**

Structure (fill every section with the real verified numbers — no placeholders survive to commit):

```markdown
# MVP Report — AI Finance Assistant

Date: 2026-07-14 · Prompts: planning 1.4.0 / system 1.5.0 · Model: llama-3.1-8b-instant (Groq)
Dataset: Northwind Manufacturing Ltd., seed=42

## 1. Verdict
The MVP hypothesis — *can an AI assistant consistently understand finance questions,
choose the right tools, reason correctly, and respond accurately on localhost?* — is
answered: **yes for honesty, grounding, and conversation quality; partially for
tool-selection consistency**, with the gaps precisely measured, reproducible, and
attributable to the 8B planning model rather than the architecture (evidence below).

## 2. Evaluation scorecard
| Metric | Result | PRD target | Met? |
|---|---|---|---|
| Eval cases passing (recorded) | 39/53 | — | — |
| Tool-selection accuracy | 76.7% | >95% (NFR-5) | ❌ |
| Parameter accuracy | 94.4% | >95% (NFR-6) | ❌ (borderline) |
| Hallucination rate | 0.0% | ~0 (NFR-7) | ✅ |
| Context retention | verified live (DEMO.md §2) | maintained (NFR-3) | ✅ |
| Backend tests | <N> passed | all | ✅ |
| Lint/types (strict) | clean, <N> files | clean | ✅ |
<how to reproduce: the three commands>

## 3. PRD success criteria
(table mapping each criterion → DEMO.md section → verdict, as in DEMO.md's summary)

## 4. Architecture audit
(the findings table from the audit working notes: rule → location → classification →
resolution; including the friendly-error fix with its commit)

## 5. Known limitations
- The 14 documented eval failures, grouped by pattern (fragment-name → search_customers
  under-routing; get_customer chaining; AR-vs-AP confusion; refusal under-trigger;
  parameter-format flakes; unrequested prefix calls) — each reproduced across 3+
  independent recordings.
- Planner nondeterminism (no temperature set; provider default ≈1.0).
- FR-9 invoice-to-PO matching not implemented (deliberately deferred; PO data exists
  in the simulator).
- FR-13 dataset actuals vs minimums (from §Step 2 counts; expense claims absent).
- Recorded Phase-2 cassettes for error-path cases predate the friendly-error fix
  (re-record folded into the next prompt-version bump).
- Carried code-level items from Milestones 4–8 (list from HANDOFF §5 last paragraph).

## 6. Post-MVP work, prioritized
1. Set Phase-1 planning temperature ≈0 in GroqLLMService + one-time full re-record —
   the single highest-leverage fix for the flake class (budget: one Groq free-tier day).
2. Prompt-harden the two systematic planner gaps (fragment-name routing, refusal
   triggering) — planning-prompt 1.5.0 candidates; each requires the eval re-run.
3. Evaluated provider/model migration (cost ladder Groq 8B $2 → Groq 70B $25 →
   Claude Haiku $72 → Claude Sonnet $216 for full 11-domain development); the
   LLMService abstraction + versioned prompts + cassette re-record make it ~1–2 days.
4. Real ERP adapters via Domain Adapters (PRD Ch.10): InvoiceAdapter interface with
   Simulator/ERPNext/SAP implementations — repositories and service adapters change,
   the AI layer and prompts do not.
5. Remaining Ch.16 finance capabilities: invoice-to-PO matching (FR-9), search_vendors.
6. Additional domains (HR, Procurement) on the platform layer + per-domain tool
   registries (the planning prompt grows with tool count).
7. Parallel tool execution; expense-claim entities; the carried code-level items (§5).
```

- [ ] **Step 4: Clean up working files and commit**

```bash
git rm docs/superpowers/plans/2026-07-14-milestone-10-audit-findings.md
rm backend/pytest_full.txt backend/pytest_output.txt backend/test_output.txt
git add docs/MVP-REPORT.md
git commit -m "docs: add MVP report (scorecard, audit results, limitations, post-MVP priorities)"
```

---

### Task 8: Fresh-environment acceptance run + HANDOFF update (acceptance criteria)

**Files:**
- Modify: `HANDOFF.md` (rewrite for Milestone 10 completion)
- Modify: `README.md` (only if the fresh run reveals a wrong/missing step)

**Interfaces:**
- Consumes: everything above. This task simulates the acceptance criterion: *a new developer can clone the repo, follow the README, and demo every success-criterion conversation on localhost within 10 minutes.*

- [ ] **Step 1: Capture anything worth keeping, then reset to a truly fresh environment**

The scorecard was persisted into MVP-REPORT (Task 7); the eval-run history in the DB will be destroyed by this step and regenerated — acceptable. **This is the one destructive step in the plan; do not skip the confirmation that MVP-REPORT is committed first** (`git log --oneline -1 -- docs/MVP-REPORT.md` shows the Task 7 commit).

```bash
docker compose down -v          # destroys the Postgres volume — fresh-clone simulation
```

- [ ] **Step 2: Follow the README verbatim, timed**

Start a timer. Execute the README's Getting started section exactly as written, in a *new* shell, character for character (fresh venv in a scratch checkout is ideal; minimum bar: fresh DB volume + `alembic upgrade head` + seed + both servers from the documented commands). Then run the README's demo command (`scripts/run_demo.py`) and ask one question in the browser UI at localhost:3000.

Expected: everything works from the documented commands alone in **under 10 minutes** (excluding raw download time on slow networks — note actuals). Every deviation = a README bug: fix `README.md` immediately and note the fix.

- [ ] **Step 3: Full final verification sweep**

```bash
cd backend
.venv/Scripts/python -m domains.finance.simulator.consistency_check
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check . ../ai_platform ../domains
.venv/Scripts/python -m mypy app alembic ../ai_platform ../domains
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m ai_platform.evaluation.run --suite core
cd ../frontend && npm run lint && npm run typecheck && npm run build
```

Expected: consistency 0 violations; all tests pass; ruff/mypy clean; eval exactly 39/53 with no STALE; frontend clean. Use the superpowers:verification-before-completion skill — paste actual outputs, no claims without evidence.

- [ ] **Step 4: Rewrite HANDOFF.md for Milestone 10**

Follow the established HANDOFF.md section structure (§1 Current State with verified-now evidence, §2 Work Completed, §3 In-Progress = nothing, §4 Decisions Made, §5 Known Issues, §6 Do NOT Do, §7 Next Steps = the MVP-REPORT §6 list). State plainly: MVP complete per PRD Ch.16 Milestone 10; deliverables DEMO.md, MVP-REPORT.md, ADRs 0005–0007, README quickstart validated at <N> minutes on a fresh environment.

- [ ] **Step 5: Final commit**

```bash
git add HANDOFF.md README.md
git commit -m "docs: Milestone 10 complete — MVP audit finished; HANDOFF updated; README validated on fresh environment"
```

- [ ] **Step 6: Finish the branch**

Use the superpowers:finishing-a-development-branch skill to decide merge/PR with your human partner. Do not push to `origin` unprompted.

---

## Self-Review (completed at planning time)

- **Spec coverage:** Item 1 (run everything, fix failures) → Task 1 (+ regression handling in Tasks 2–3, final sweep in Task 8). Item 2 (scripted demos per PRD criterion → DEMO.md) → Task 4, all five criteria mapped. Item 3 (architecture grep audit, fix findings) → Task 2 + Task 3 (the one pre-known violation). Item 4 (README <10 min, per-component docs, ADRs) → Tasks 5–6, validated in Task 8. Item 5 (MVP-REPORT: scorecard, limitations, prioritized post-MVP) → Task 7. Acceptance criterion (fresh developer, 10 minutes) → Task 8.
- **Deliberate scope exclusions (documented, not built):** FR-9 PO matching, search_vendors, temperature change + re-record, prompt hardening — all recorded as post-MVP priorities per HANDOFF §7; building them would trigger prompt bumps/re-records this milestone forbids.
- **Type consistency:** `user_error_message: str | None = None` is the same name/type in the executor dataclass (Task 3 Step 3), workflow construction site (Step 7), and all tests (Steps 1, 5). `_build_response_message(message: str, outcomes: list[ToolExecutionOutcome]) -> str` signature unchanged.
- **Known verification points that may need in-flight adjustment (flagged in-task, not placeholders):** psql user/db names (verify from docker-compose.yml/.env), evaluation_runs column names (verify from models.py), mypy coverage of `backend/scripts/` (match existing config), exact `-k` expression for the new tests.
