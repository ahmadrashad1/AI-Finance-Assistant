.PHONY: dev-backend dev-frontend db-up db-down test lint

# Assumes the backend virtualenv is activated (see backend/README.md) and
# frontend dependencies are installed (npm install in frontend/).

dev-backend:
	cd backend && uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

db-up:
	docker compose up -d

db-down:
	docker compose down

test:
	cd backend && python -m pytest

lint:
	cd backend && python -m ruff check . && python -m mypy app alembic
	cd frontend && npm run lint && npm run typecheck
