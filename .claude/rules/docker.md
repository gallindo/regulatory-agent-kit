---
description: Docker and container rules
globs: ["docker/**", "docker-compose.yml", "Dockerfile*"]
---

# Docker Rules

- Base image: `python:3.12-slim` (multi-stage builds for worker and API)
- Run as non-root user `rak` (UID 1000) — never run containers as root
- Install dependencies from `requirements.txt` in builder stage, copy site-packages to runtime stage
- Health checks required for stateful services (postgres, elasticsearch)
- Use named volumes for persistent data (postgres_data, es_data, prometheus_data, grafana_data)
- Environment variables injected via `.env` file — never bake secrets into images
- `docker/init-db.sql` creates `temporal` and `mlflow` databases — the `rak` database is created by POSTGRES_DB env var
