# HANDOFF — AI Finance Assistant MVP
Last updated: 2026-07-05 | Current milestone: 1 — Project Foundation | Status: complete

## 1. Current State

Verified working right now (re-ran everything before writing this doc):

- `docker compose up -d` — Postgres 16 healthy (`docker compose ps` shows `Up ... (healthy)` on `5432`).
- Backend: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload` (or `python -m venv .venv && pip install -e ".[dev]"` first if no venv yet) → `GET /api/health` returns `{"status":"healthy","app":"ok","database":"ok"}` against the real DB.
- Frontend: `cd frontend && npm install && npm run dev` → `http://localhost:3000` renders "AI Finance Assistant" and, once the fetch resolves, "Backend status: healthy (database: ok)" — confirmed in an actual browser (Playwright), not just curl.
- Backend tests: `cd backend && .venv/Scripts/python -m pytest` → **24 passed**.
- Backend lint/types: `ruff check .` → clean; `mypy app alembic` → clean (strict mode).
- Frontend lint/types: `npm run lint` (ESLint flat config) → clean; `npm run typecheck` → clean; `npm run build` → succeeds.
- **No seed script exists yet** — no ORM models exist, so there's nothing to seed (lands in Milestone 4, Finance Simulator).
- **No AI evaluation suite exists yet** — `platform/evaluation/` is still just a README placeholder (lands in Milestone 8). Only pytest unit/integration tests exist today.
- **No `make` binary on this Windows dev box** — verified the `Makefile` recipes by running their underlying commands directly. CI (`.github/workflows/ci.yml`, Linux) exercises `make`-equivalent steps directly too (doesn't call `make` itself either — see §5).

## 2. Work Completed This Session

- Repo scaffold: `platform/{orchestration,workflow,tool_registry,evaluation,memory}/`, `domains/{finance/{tools,services,simulator}}/` — all README-only placeholders, no code yet.
- `CLAUDE.md` (non-negotiable rules) and `docs/adr/000{1,2,3,4}-*.md` (FastAPI-as-orchestrator, two-phase LLM execution, simulator-over-ERP, tool registry).
- Backend (`backend/app/`), all TDD (test written and watched red before implementation):
  - `core/config.py` — Pydantic v2 `Settings` (`DATABASE_URL` required; `LLM_PROVIDER`/`LLM_API_KEY`/`LLM_MODEL`/`LOG_LEVEL`/`CORS_ALLOWED_ORIGINS` with defaults).
  - `core/logging.py` — `JSONFormatter` + `request_id_ctx_var`/`conversation_id_ctx_var`/`workflow_ctx_var` (the latter two unused until Milestone 2+ but wired now).
  - `core/errors.py` — `ErrorCategory` (StrEnum: validation/business/infrastructure/ai/unexpected), `AppError` + 4 subclasses, `register_exception_handlers()`.
  - `middleware/request_context.py` — `RequestContextMiddleware` (generates/echoes `X-Request-ID`, logs completion line).
  - `db/base.py`, `db/session.py` — async SQLAlchemy engine/session, `check_database_connection()`.
  - `api/health.py` — `GET /health` (mounted at `/api/health`).
  - `main.py` — wires CORS → RequestContext → error handlers → health router.
  - `alembic/` — async-engine `env.py` wired to `Settings`/`Base.metadata`; `alembic/versions/` empty (no models yet).
  - `tests/` — 24 tests across `test_config.py`, `test_logging.py`, `test_errors.py`, `test_request_context.py`, `test_db_session.py`, `test_health.py`, `test_cors.py`.
- Frontend (`frontend/`): `app/layout.tsx`, `app/page.tsx` (placeholder, calls backend), `lib/api-client.ts` (typed `getHealth()`), `eslint.config.mjs` (flat config, replaced incompatible `.eslintrc.json`), strict `tsconfig.json`.
- Root: `docker-compose.yml` (Postgres 16), `Makefile` (`dev-backend`/`dev-frontend`/`db-up`/`db-down`/`test`/`lint`), `.github/workflows/ci.yml`.
- No prompt files exist yet (no LLM calls implemented) — nothing to version.
- No migrations added — no ORM models exist yet.
- Commits: `2921418` (scaffold), `059b0a1` (Milestone 1 implementation).

## 3. In-Progress Work (exact stopping point)

**Nothing is mid-implementation.** Milestone 1 is fully complete, committed, and clean (`git status` is clean at `059b0a1`). The next session starts fresh on Milestone 2 (see §7) — there is no partially-edited file to resume.

## 4. Decisions Made

- CORS origins configured as a comma-separated string field (`cors_allowed_origins: str`) with a `.cors_allowed_origins_list` property, not a native `list[str]` pydantic-settings field — avoids JSON-vs-CSV env-var parsing ambiguity. Implementation detail, no ADR needed.
- Health check DB status is injected via FastAPI `Depends(check_database_connection)` specifically so tests can override it — avoids requiring a live Postgres for the test suite. Implementation detail, no ADR needed.
- `/api/health` never raises on DB failure; it reports `"degraded"` — matches NFR-11 (graceful error handling) from the PRD. Consistent with existing ADR-0001, no new ADR needed.
- Middleware order in `main.py` is CORS added first, then `RequestContextMiddleware` — because Starlette's `add_middleware` does `list.insert(0, ...)`, the *last* added ends up outermost. Worth a one-line comment if this trips up the next person (already commented in `main.py`).
- No new ADR-worthy architectural decisions this session — everything fits within ADR-0001..0004.

## 5. Known Issues / Failing Tests

- **None.** All 24 backend tests pass, ruff/mypy/ESLint/tsc are all clean as of this writing.
- Environment quirk (not a code bug): this Windows sandbox got a stuck stale socket on port 8000 after repeated manual server restarts during verification (dead PID, but Windows still reported the port bound — `WinError 10048`). Not present in a normal dev workflow; if it recurs, use a different `--port` or reboot rather than debugging the app code.
- `platform/evaluation/`, `platform/tool_registry/`, `platform/memory/`, `platform/orchestration/`, and all of `domains/finance/` are still README-only — expected for this milestone, listed here so it's not mistaken for an oversight.

## 6. Do NOT Do

- Don't add `.eslintrc.json` back — this project's ESLint is v9 (flat config only). Use `frontend/eslint.config.mjs`.
- Don't add finance tools/services/simulator code yet — the roadmap (PRD Ch. 16) puts the Finance Simulator at Milestone 4 and the first real tool at Milestone 5. Milestone 2 is chat-only, no finance capability.
- Don't let the LLM call tools directly or skip the planning/response split once chat lands in Milestone 2 — non-negotiable per `CLAUDE.md` (two-phase execution, FastAPI orchestrates).
- Don't skip TDD on new backend modules — every existing module was built red-then-green; keep that pattern (see `superpowers:test-driven-development`).
- Don't assume `make` works on this machine without checking — it isn't installed here; verify via the underlying commands if in doubt.
- Don't reintroduce `list[str]` for `CORS_ALLOWED_ORIGINS` in `Settings` without checking pydantic-settings' env parsing — the comma-separated-string-plus-property approach was chosen deliberately (see §4).

## 7. Next Steps (prioritized)

Milestone 2 — Basic AI Chat (PRD Ch. 16 "Milestone 2"; design detail in Ch. 8 AI Architecture, Ch. 13 AI Request Lifecycle, Ch. 15 Frontend Architecture):

1. Add `conversations`/`messages` ORM models (PRD Ch. 12, "Application Data") — first real use of `backend/app/db/base.py` and the first Alembic migration (`alembic revision --autogenerate`, then apply it).
2. Implement conversation memory (`platform/memory/`) — selective retrieval, not "send everything" (PRD Ch. 13 "Memory Strategy").
3. Add an LLM client wrapper (provider-agnostic; `LLM_PROVIDER`/`LLM_API_KEY`/`LLM_MODEL` already in `Settings`) and a `POST /api/chat` endpoint built as a workflow following Initialize → Validate → Execute → Log → Evaluate → Complete (`CLAUDE.md` workflow lifecycle rule) — TDD, same as Milestone 1.
4. No tool calls yet at this milestone (that's Milestone 3, `get_current_date()` as the toy tool) — Milestone 2 is plain conversational chat, streamed.
5. Replace the frontend placeholder page with a real chat UI (message list, input, streaming) per PRD Ch. 15; keep `lib/api-client.ts` as the single point of contact with the backend.
6. Write unit + integration tests test-first for every new module, same pattern as Milestone 1's 24 tests. AI evaluation cases are still deferred to Milestone 8 — don't add an eval framework yet, just don't regress the "always demonstrable" rule.
