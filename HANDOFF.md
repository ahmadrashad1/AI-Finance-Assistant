# HANDOFF — AI Finance Assistant MVP
Last updated: 2026-07-14 | Current milestone: 10 — MVP Completion Audit | Status: **complete — MVP done**

## 1. Current State

Verified working right now — on a database rebuilt **from zero** this session
(`docker compose down -v` → up → migrate → seed), not a carried-over volume:

- `docker compose ps` — Postgres 16 healthy on `0.0.0.0:5432` (fresh volume, 8s to healthy).
- `alembic upgrade head` from an empty database → all migrations apply cleanly; `python -m domains.finance.simulator.seed` → `Seeded Northwind Manufacturing Ltd. (seed=42).` (migrate+seed: 3s).
- Backend tests: `cd backend && .venv/Scripts/python -m pytest -q` → **445 passed**, ~112s (440 at milestone start — Milestone 9's HANDOFF said 439 but its final commit added the CORS test after the count was written; +5 new friendly-error tests this milestone).
- Lint/types: ruff `All checks passed!`; mypy strict `Success: no issues found in 106 source files`.
- Frontend: lint, typecheck, build all clean.
- Consistency: `Consistency check passed: 0 violations.`
- Eval suite: `python -m ai_platform.evaluation.run --suite core` → **39/53, tool-selection 76.7%, parameters 94.4%, hallucination 0.0%, no STALE** — identical before and after every change this milestone (the friendly-error fix cannot stale cassettes: they key on `case_id+turn+prompt-version hash`).
- **Live acceptance turn on the fresh DB**: *"Which customers haven't paid us?"* → planned `get_unpaid_invoices`, executed in 12ms, total 1445ms, correct table; trace API confirmed branch/versions/timing. Frontend served HTTP 200 on :3000.
- Git: all Milestone 10 work on branch **`milestone-10-mvp-completion-audit`** (10 commits), ready for merge review. Working tree clean except pre-existing local items (`.claude/settings.json`, user's `docs/execution-prompt.md`).

## 2. Work Completed This Session (Milestone 10 — the five audit items)

1. **Full verification run** (item 1): clean-slate baseline re-proven, then re-proven again at the end on a from-zero database. No regressions; the 14 eval failures match Milestone 9's documented findings exactly.
2. **PRD success criteria demos → `docs/DEMO.md`** (item 2): five scripted conversations via the new `backend/scripts/run_demo.py` (drives `POST /api/chat` SSE + `GET /api/trace/{request_id}` per turn; paces turns and retries on provider-busy). All five criteria demonstrated live; **every factual claim SQL-cross-checked and exact** (aging buckets cell-for-cell, duplicates group-for-group, cash $918,201.30, Anchor balance $188,446.50, unpaid 87/$2,650,349.70). Known gaps shown honestly in the document (fragment names, cross-turn step piping, two one-off Phase-2 numeric prose garbles).
3. **Architecture audit** (item 3): grep sweep + endpoint review + prompt-history audit. One genuine violation — the pre-known HANDOFF-§5 raw-error leak — **fixed with TDD**: `ToolExecutionOutcome.user_error_message` (business `ValueError`s pass through, e.g. "Customer not found: Anchor"; Pydantic dumps/`$stepN` references/unexpected exceptions masked with categorized friendly text); Phase 2 and users never see internals, developers keep full detail in logs/`tool_executions`/traces. Verified live. Two judgment calls documented (simulator CLI SQL; platform→app shared-infra imports). Everything else clean — full table in `docs/MVP-REPORT.md` §4.
4. **Documentation** (item 4): root README rewritten (real layout with `ai_platform/`, ~10-minute quickstart validated this session, demo/tests/eval commands, MVP-complete status); all component READMEs refreshed to Milestone-9 reality; new `ai_platform/llm/README.md` and `ai_platform/prompts/README.md`; **ADRs 0005–0007** added (cassette record/replay evaluation, out-of-scope refusal as plan branch, request-traces table).
5. **`docs/MVP-REPORT.md`** (item 5): scorecard vs PRD targets stated plainly (hallucination 0.0% met; tool-selection 76.7% vs >95% not met — attributed to the 8B planner with an evaluated migration path; parameters 94.4% borderline), the 14 failures by pattern, FR-9/FR-13 gaps, carried code-level items, and an 8-point prioritized post-MVP list.

## 3. In-Progress Work

**Nothing is mid-implementation.** The milestone plan
(`docs/superpowers/plans/2026-07-14-milestone-10-mvp-completion-audit.md`)
is fully executed. The branch awaits merge review.

## 4. Decisions Made

- **Friendly errors are a code-level contract, not a prompt change**: the fix lives in the executor/workflow (`user_error_message`), so no prompt bump, no cassette re-record. Recorded Phase-2 responses for error-path cases predate the fix — live behavior is friendlier than those recordings; re-record folds into the next prompt bump.
- **Business `ValueError`s pass through to users verbatim** — services already phrase them user-appropriately ("Customer not found: X"). Everything else is masked by category.
- **The 14 eval failures stay failing** and are shipped as documented findings in MVP-REPORT (never-loosen-expectations rule).
- **Demo transcripts are honest, with one re-roll allowed per demo** (planner samples at default temperature): re-rolls that expose documented gaps are kept and labeled, not discarded; first-roll numeric garbles are documented in DEMO.md and MVP-REPORT even though the re-roll was clean.
- **FR-9 (PO matching) and FR-13 (dataset minimums) are documented gaps, not silent fixes** — building them mid-audit would violate the milestone's scope and the prompt-bump budget.
- **A secondary Groq key (user-supplied) finished the demo runs** after the primary account's daily budget exhausted — env-var override only, never written to `.env`, never committed; the override server was stopped afterwards.

## 5. Known Issues / Failing Tests

- **No test/lint/type failures.** 445 backend tests pass; ruff/mypy clean; frontend clean.
- **The 14 documented eval failures (39/53)** — unchanged from Milestone 9, full pattern breakdown in `docs/MVP-REPORT.md` §5: fragment-name → `search_customers` under-routing (5), `get_customer` chaining (3), AR-vs-AP confusion (1), refusal under-trigger (2), parameter-format flake (1), unrequested prefix call (1), `ambiguous_show_invoices` (1).
- **Phase-2 numeric prose flakes** (new, observed live once each, documented in DEMO.md §3): a garbled total and an invented count in free prose above/below correct structured tables. Structured figures quoted from tool summaries were reliable in every observation.
- **Cross-turn `$stepN` references** (documented): the planner sometimes pipes from a previous turn's plan; resolves to a friendly resolution-error and an honest reply.
- **Planner nondeterminism unmitigated** (no temperature set) — §7.1 remains the highest-leverage fix.
- **Carried code-level items from Milestones 4–8** — unchanged, listed in MVP-REPORT §5.

## 6. Do NOT Do

- **Don't run pytest (or anything using `clean_db`) between reseeding and anything that reads seeded data** (demos, recording, manual verification) — it truncates the finance tables.
- **Don't run two recording/demo processes concurrently; don't assume a killed background shell killed its children** — verify with `tasklist | findstr python` (this session: a killed `npm run dev` left a node child holding :3000 — kill by PID from `netstat -ano`, never kill all node.exe, the user's editor runs node too).
- **Don't treat rate-limited output as model behavior** — Groq free tier is ~6k tokens/min *and* 500k/day (sliding); each chat turn costs ~5–9k tokens. `scripts/run_demo.py` paces turns (default 60s) and retries once on busy; a full demo run needs ~150k tokens of daily headroom.
- **Don't loosen eval expectations; don't bump prompt `VERSION`s casually** (full re-record ≈ a Groq free-tier day); **keep eval case ids ≤44 chars**; **don't hand-script cassettes** — all carried forward, all still true.
- **Don't commit API keys** — the secondary-key pattern is env-var override only.
- **Don't push to `origin` without being asked.** Don't assume Docker Desktop is running.

## 7. Next Steps (prioritized — same list as MVP-REPORT §6)

1. **Planning temperature ≈0** in `GroqLLMService` + one-time full re-record — the single highest-leverage quality fix.
2. **Prompt-harden fragment-name routing and refusal triggering** (planning-prompt 1.5.0 candidates; each requires the re-record + re-run).
3. **Evaluated provider/model migration** (Groq 70B / Claude Haiku / Claude Sonnet ladder) to close the tool-selection gap toward NFR-5's >95%.
4. **Domain Adapters (PRD Ch.10)** for real ERP integration.
5. **FR-9 PO matching, `search_vendors`, simulator size profiles (FR-13).**
6. **HR/Procurement domains + per-domain tool registries.**
7. **Extract shared infra out of `backend/app`** (audit §4.7 debt) so the platform no longer imports from the app.
8. **Parallel tool execution** + carried code-level items.
