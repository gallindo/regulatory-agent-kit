# ---------------------------------------------------------------
# regulatory-agent-kit — Makefile
# ---------------------------------------------------------------
# Alternative to justfile for environments without just installed.
# ---------------------------------------------------------------

.PHONY: install test test-cov lint fix typecheck check up down build migrate

install:
	uv sync --all-extras

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=regulatory_agent_kit --cov-report=term-missing

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

fix:
	ruff check --fix src/ tests/
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint typecheck test

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

migrate:
	alembic upgrade head
