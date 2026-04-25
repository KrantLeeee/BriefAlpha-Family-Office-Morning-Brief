.PHONY: dev dev-api dev-web dev-redis init-secrets db-migrate db-revision \
	test test-api test-web lint typecheck

PYTHON ?= python3.11
UV ?= uv

dev:
	@echo ">> Start redis (`make dev-redis`), backend (`make dev-api`), and frontend (`make dev-web`) in separate shells."

dev-api:
	cd apps/api && $(UV) run uvicorn briefalpha_api.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	pnpm --filter @briefalpha/web dev

dev-redis:
	redis-server --port 6379 --daemonize no

init-secrets:
	bash scripts/init_secrets.sh

db-migrate:
	cd apps/api && $(UV) run alembic upgrade head

db-revision:
	cd apps/api && $(UV) run alembic revision --autogenerate -m "$(M)"

test: test-api test-web

test-api:
	cd apps/api && $(UV) run pytest

test-web:
	pnpm --filter @briefalpha/web test:e2e

lint:
	pnpm lint

typecheck:
	pnpm typecheck
