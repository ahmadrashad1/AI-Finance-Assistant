# Frontend (Next.js)

A thin presentation layer: chat interface, markdown/table rendering, and
conversation UI state. It never contains business logic, never decides
which tools to call, and never talks directly to PostgreSQL — everything
goes through the FastAPI backend.

A placeholder home page (`app/page.tsx`) confirms connectivity to the FastAPI
backend via `lib/api-client.ts`, a typed fetch wrapper. TypeScript/ESLint
tooling is configured in `tsconfig.json` and `eslint.config.mjs`.
