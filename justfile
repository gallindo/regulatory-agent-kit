# ---------------------------------------------------------------
# regulatory-agent-kit — Development Task Runner
# ---------------------------------------------------------------
# Install just: https://github.com/casey/just
# Usage: just <recipe>
# ---------------------------------------------------------------

default:
    @just --list

# Install all dependencies (including dev)
install:
    uv sync --all-extras

# Run the full test suite
test:
    pytest tests/ -v

# Run tests with coverage report
test-cov:
    pytest tests/ --cov=regulatory_agent_kit --cov-report=term-missing

# Run only unit tests
test-unit:
    pytest tests/unit/ -v

# Run only integration tests (requires Docker services)
test-integration:
    pytest tests/integration/ -v -m integration

# Lint and format check
lint:
    ruff check src/ tests/
    ruff format --check src/ tests/

# Auto-fix lint issues and format
fix:
    ruff check --fix src/ tests/
    ruff format src/ tests/

# Type check
typecheck:
    mypy src/

# Run all quality checks
check: lint typecheck test

# Start all services (Docker Compose)
up:
    docker compose up -d

# Stop all services
down:
    docker compose down

# View service logs
logs *args:
    docker compose logs {{ args }}

# Build Docker images
build:
    docker compose build

# Run database migrations
migrate:
    alembic upgrade head

# Create a new migration
migration name:
    alembic revision --autogenerate -m "{{ name }}"

# Run the CLI in Lite Mode
run-lite regulation *repos:
    python -m regulatory_agent_kit.cli run --lite --regulation {{ regulation }} --repos {{ repos }}
