# Milestone 10 audit — working notes

Working file for the MVP completion audit. Folded into `docs/MVP-REPORT.md` (Task 7)
and deleted before the milestone closes.

## Baseline (Task 1, 2026-07-14, branch `milestone-10-mvp-completion-audit` off master `6c264f3`)

- Docker: `ai-financeassistant-postgres-1` healthy (Postgres 16, 0.0.0.0:5432)
- Reseed: `Seeded Northwind Manufacturing Ltd. (seed=42).`
- Consistency: `Consistency check passed: 0 violations.`
- pytest: **440 passed** in 110s. (HANDOFF.md said 439 — the final Milestone 9 commit
  `6c264f3` added the failing-first CORS test in the same commit that wrote HANDOFF,
  so its count was one stale. Not a regression.)
- ruff (`. ../ai_platform ../domains`): `All checks passed!`
- mypy strict (`app alembic ../ai_platform ../domains`): `Success: no issues found in 106 source files`
- frontend: `npm run lint` clean, `npm run typecheck` clean, `npm run build` compiled
- eval `--suite core` recorded: **39/53** | tool-selection **76.7%** | parameters **94.4%**
  | memory 0.0% | hallucination **0.0%**
- stale cassettes: **none** (0 STALE lines in report)

## Architecture audit findings (Task 2)

Grep sweep run 2026-07-14 from repo root. Every hit classified; commands recorded in
the Milestone 10 plan (Task 2 steps 1–7).

| # | Rule | Location | Classification | Resolution |
|---|------|----------|----------------|------------|
| 1 | Friendly errors ("Users get a friendly message") | `ai_platform/orchestration/chat_workflow.py:46-58,151-161`; `ai_platform/tool_registry/executor.py:56-75` | **Violation** (pre-known, HANDOFF §5: Phase 2 quotes raw `$step0.*` / Pydantic internals to users) | Fixed in Task 3 |
| 2 | SQL outside repositories | `domains/finance/simulator/{seed,consistency_check,generator,profile_request}.py` | Judgment call — the simulator **is** the dev-ERP stand-in below the repository boundary; these are CLI bootstrap/integrity tools, never on the request path. Tools/services/endpoints: **clean** | Documented; no change |
| 3 | SQL outside repositories (false positives) | `chat_workflow.py:85,164`, `executor.py:65`, `workflow/base.py:51` | False positive — `Context(`/`.execute(` of the tool executor matched the regex, no SQL | None |
| 4 | Prose generated inside tools | `domains/finance/tools/` | **Clean** — no string returns; all tools return Pydantic result models | None |
| 5 | Keyword matching | `evaluation/scoring.py` (eval harness regex vs expectations), `execution_planner.py:8` (`$stepN.field` plan-JSON syntax), `planner.py:51-55` (markdown-fence stripping of LLM output), `customer/vendor_repository.py` (`func.lower` data matching), generator emails, logging level | All judgment calls/false positives — none touch the *user's message*; intent understanding is exclusively the LLM's. **No intent-by-keyword anywhere** | None |
| 6 | Business logic in endpoints | `backend/app/api/{chat,trace,health}.py` (all read in full) | **Clean** — receive → delegate (workflow/repository) → typed response; `post_chat`'s object construction is DI wiring | None |
| 7 | Unversioned prompt edits | full `git log --follow` on both prompt files | **Clean** — every content change carries a VERSION bump + changelog (`d27ed2a` bumped 1.2.0→1.3.0 despite the commit title; `5f54268` changed only the builder signature, template untouched, and the behavior rule shipped with the 1.3.0 bump). Current 1.4.0/1.5.0 match the latest eval run | None |
| 8 | Layering direction | `ai_platform/` and `domains/` import `app.db.base.Base`, `app.core.errors`, `app.core.logging`, `app.db.session` (21 imports) | Judgment call — **architectural debt**: the reusable platform depends on the FastAPI app package for shared infrastructure (declarative Base, error categories, logging ctx vars, sessionmaker). The enumerated CLAUDE.md layering (endpoints→workflows→services→repositories) is satisfied; the debt is that "shared" infra lives under `app/`. Refactor = ~21-file move mid-audit for zero user value | Documented as post-MVP: extract shared infra into `ai_platform.core` (or `shared/`) |
| 9 | Banned names (Manager/Helper/Utils/Processor) | — | **Clean** | None |
| 10 | `print()` in request paths | only CLI entry points (eval `run.py`, seed, consistency_check, profile_request) | **Clean** — request path uses structured logging | None |

**Net result:** one genuine violation (row 1, pre-known, fixed in Task 3); two documented
judgment calls (rows 2, 8); everything else clean.

## FR-13 dataset counts (Task 7 input, seed=42, verified via psql 2026-07-14)

| Entity | Seeded | FR-13 minimum | Met? |
|---|---|---|---|
| customers | 25 | 500 | ❌ |
| vendors | 15 | 150 | ❌ |
| invoices | 205 (+33 vendor invoices) | 10,000 | ❌ |
| purchase_orders | 40 | 3,000 | ❌ |
| payments | 141 (+23 vendor payments) | 2,500 | ❌ |
| expense_claims | 60 | 500 | ❌ |
| employees / products | 20 / 15 | — | — |

The seed CLI has no size/profile option (`--reset`, `--seed` only) — the PRD Ch.11
"small/medium/large" generator profiles are unimplemented. The compact dataset is
internally consistent (0 violations) and every eval case is authored against it, but
FR-13's minimum counts are not met. Known limitation for MVP-REPORT §5.

## Demo evidence salvaged so far (Task 4, in progress — blocked on Groq daily budget)

Live turns completed 2026-07-14 before the daily 500k-token budget exhausted
(instant 429s on every request thereafter; per HANDOFF §6 rate-limited output is
never treated as model behavior). All SQL cross-checks passed **exactly**:

1. **"Show unpaid invoices."** → planned `get_overdue_invoices()`; reply table's rows
   (INV-7051 $21,060, INV-7014 $6,534, INV-7154 $72,063, ...), count 80, and total
   $2,506,110.30 all match `finance.invoices WHERE status='overdue'` exactly.
   Full transcript + trace JSON captured. (Note: rolled get_overdue_invoices rather
   than get_unpaid_invoices this roll — nondeterminism; the eval suite's
   unpaid_invoices category, 5/5 recorded, is the paraphrase-invariance proof.)
2. **"Which customers haven't paid us?"** → planned `get_unpaid_invoices()`
   (trace recovered from request_traces; Phase 2 lost to 429).
3. **"Show invoices overdue by more than 60 days"** → planned
   `get_overdue_invoices(minimum_days=61)` — correct tool + correct exclusive-bound
   parameter (trace recovered from request_traces; Phase 2 lost to 429).
4. **"Show me invoices for Anchor Components"** → planned `get_customer("Anchor
   Components")` then `search_invoices(customer_id=$step0.customer_code)` — two-step
   chain executed (CUST-0003), reply's 8 invoices / $274,617.00 total match SQL
   exactly, row-for-row. Full transcript + trace JSON captured.
5. **Friendly-error live check** (Task 3): honest "Customer not found: Anchor" reply
   with zero internals.

Zero hallucinated values across every captured turn.

Remaining turns needed for docs/DEMO.md (multi-turn follow-ups, aging report,
duplicates, cash position, INV-99999 honesty, $10M empty-result honesty,
fragment-name gap, aging explanation, out-of-scope refusal): **blocked until the
Groq daily window refills or a secondary key is provided** (same blocker and same
resolution path as Milestone 9's recording session).

## Latest evaluation run (evaluation.evaluation_runs, authoritative scorecard)

`core | recorded | 53 total | 39 passed | overall_score 0.7358 | prompts 1.4.0/1.5.0 | 2026-07-14 07:44 UTC`

## Friendly-error fix verification (Task 3)

- TDD: 3 new executor tests + 2 new `_build_response_message` tests, failing-first, now
  green; 1 existing test (`test_unresolvable_reference_degrades_gracefully...`) updated
  to pin the new friendly contract (deliberate contract change, not expectation-loosening
  — eval expectations untouched).
- Full suite after fix: **445 passed**; ruff/mypy clean (106 files).
- Eval recorded after fix: **39/53, 76.7%/94.4%/0.0%, no STALE** — unchanged, as designed
  (cassettes key on case+turn+prompt-hash, not request content).
- Live repro (HANDOFF §5): *"What is Anchor's current outstanding balance?"* →
  `get_customer_balance` failed with the business error and the streamed reply was:
  > Unfortunately, I'm unable to find the current outstanding balance for Anchor. The
  > tool result indicates an error: "Customer not found: Anchor".
  No `$step0`, no `Tool '...' failed:`, no Pydantic internals. Guardrails intact.
- Known drift (documented, acceptable): recorded Phase-2 cassettes for error-path cases
  were recorded against the old raw error text; live behavior is now friendlier. A
  re-record folds into the next prompt-version bump.
