# Local Development with Docker Compose

> **Time to first run:** ~10 minutes
> **Prerequisites:** Docker Engine 24+ with Compose V2, an LLM API key, Git
> **RAM required:** 12 GB minimum (16 GB recommended)
> **Glossary:** See [`glossary.md`](glossary.md) for term definitions.

This guide gets you a fully-featured `regulatory-agent-kit` environment on your local machine — all services running, parallel processing, Elasticsearch semantic search, MLflow tracing, and Temporal workflow orchestration. You only need to edit two files.

For a lighter evaluation without Docker, see [`getting-started.md`](getting-started.md) (Lite Mode, 5 minutes, no infrastructure).

---

## Table of Contents

1. [Quick Start (3 Steps)](#1-quick-start-3-steps)
2. [Configuration Reference](#2-configuration-reference)
3. [What's Running](#3-whats-running)
4. [Using the Pipeline](#4-using-the-pipeline)
5. [Stopping and Cleaning Up](#5-stopping-and-cleaning-up)
6. [Troubleshooting](#6-troubleshooting)
7. [Next Steps](#7-next-steps)

---

## 1. Quick Start (3 Steps)

### Step 1: Set your secrets

Copy the secrets template and fill in your LLM API key:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# Required — pick at least one LLM provider
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OPENAI_API_KEY=sk-your-key-here

# Optional — for private Git repositories
# GITHUB_TOKEN=ghp_your-token-here
# GITLAB_TOKEN=glpat-your-token-here
```

> **Security:** `.env` is listed in `.gitignore`. Never commit API keys.

### Step 2: Configure your pipeline

Copy the configuration template and edit it:

```bash
cp rak-config.yaml.example rak-config.yaml
```

Edit `rak-config.yaml`:

```yaml
# ---------------------------------------------------------------
# regulatory-agent-kit — Pipeline Configuration
# ---------------------------------------------------------------
# Edit this file, then run: docker compose up
# Full reference: docs/local-development.md#2-configuration-reference
# ---------------------------------------------------------------

# Which regulation plugin to enforce
regulation: regulations/dora/dora-ict-risk-2025.yaml

# Repositories to analyze (HTTPS URLs or local paths mounted into the container)
repos:
  - https://github.com/your-org/service-a
  - https://github.com/your-org/service-b
  # - /workspace/local-repo    # mount via docker-compose.override.yml

# LLM model for analysis (any LiteLLM-supported model identifier)
model: anthropic/claude-sonnet-4-6

# How you approve checkpoints: terminal | slack | email | webhook
checkpoint_mode: terminal

# Maximum estimated LLM cost (USD) before the pipeline asks for approval
cost_threshold: 5.00
```

That's it — the only file you need to customize.

### Step 3: Start everything

```bash
docker compose up -d
```

First run pulls images and initializes databases (~3-5 minutes). Subsequent starts take ~15 seconds.

Verify all services are healthy:

```bash
docker compose ps
```

You should see all services in `running` state. Then trigger your first pipeline:

```bash
# Using the CLI (installed in the worker container)
docker compose exec worker rak run \
  --config /app/rak-config.yaml

# Or via the API
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"regulation_id": "dora-ict-risk-2025", "change_type": "new_requirement"}'
```

---

## 2. Configuration Reference

### `rak-config.yaml` — Full Field Reference

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `regulation` | `string` | **Yes** | — | Path to the regulation plugin YAML file, relative to the project root. |
| `repos` | `list[string]` | **Yes** | — | Repository URLs (HTTPS) or local paths to analyze. |
| `model` | `string` | No | `anthropic/claude-sonnet-4-6` | LLM model identifier. Any [LiteLLM-supported model](https://docs.litellm.ai/docs/providers). |
| `checkpoint_mode` | `string` | No | `terminal` | How human approvals are collected. Options: `terminal`, `slack`, `email`, `webhook`. |
| `cost_threshold` | `number` | No | `5.00` | Maximum estimated LLM cost (USD) before requiring explicit cost approval. Set to `0` to always require approval. |
| `auto_approve_cost` | `boolean` | No | `false` | If `true`, skip the cost approval checkpoint when the estimate is below `cost_threshold`. |
| `max_retries` | `integer` | No | `3` | Maximum retry attempts for failed agent activities (test failures, LLM errors). |
| `slack_channel` | `string` | No | — | Slack channel for checkpoint notifications. Required if `checkpoint_mode: slack`. |
| `slack_webhook_url` | `string` | No | — | Slack incoming webhook URL. Required if `checkpoint_mode: slack`. |
| `email_recipients` | `list[string]` | No | — | Email addresses for checkpoint notifications. Required if `checkpoint_mode: email`. |
| `webhook_url` | `string` | No | — | Callback URL for checkpoint notifications. Required if `checkpoint_mode: webhook`. |

### `.env` — Secrets Reference

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (or another LLM key) | Anthropic API key for Claude models. |
| `OPENAI_API_KEY` | No | OpenAI API key (alternative or fallback provider). |
| `GITHUB_TOKEN` | No | GitHub personal access token for private repositories. |
| `GITLAB_TOKEN` | No | GitLab personal access token for private repositories. |
| `POSTGRES_PASSWORD` | No | PostgreSQL password. Default: `rak_dev_password`. |
| `ELASTICSEARCH_PASSWORD` | No | Elasticsearch password. Default: `rak_dev_password`. |

---

## 3. What's Running

After `docker compose up`, you have the following services:

| Service | Port | URL | Purpose |
|---|---|---|---|
| **RAK API** | 8000 | [http://localhost:8000](http://localhost:8000) | Webhook events, approvals, pipeline status |
| **RAK Worker** | — | (no UI) | Temporal worker — executes workflows, activities, and agents |
| **Temporal Server** | 7233 | (gRPC, no browser UI) | Workflow engine — manages state, retries, scheduling |
| **Temporal UI** | 8080 | [http://localhost:8080](http://localhost:8080) | Workflow visibility — see running/failed/completed pipelines |
| **PostgreSQL** | 5432 | — | Database for Temporal, RAK, and MLflow schemas |
| **Elasticsearch** | 9200 | [http://localhost:9200](http://localhost:9200) | Regulatory knowledge base (semantic search) |
| **LiteLLM Proxy** | 4000 | [http://localhost:4000](http://localhost:4000) | LLM gateway — routes calls to your configured provider |
| **MLflow** | 5000 | [http://localhost:5000](http://localhost:5000) | LLM observability — traces, token usage, cost tracking |
| **Prometheus** | 9090 | [http://localhost:9090](http://localhost:9090) | Operational metrics collection |
| **Grafana** | 3000 | [http://localhost:3000](http://localhost:3000) | Dashboards (login: `admin` / `admin`) |

### Useful UIs to Explore

- **Temporal UI** (`localhost:8080`) — Watch your pipeline progress in real-time. See which repositories are being processed, where checkpoints are waiting, and which activities have failed.
- **MLflow** (`localhost:5000`) — After a pipeline run, inspect every LLM call: prompts, completions, token counts, costs, and latency.
- **Grafana** (`localhost:3000`) — Pre-built dashboards for pipeline throughput, error rates, and LLM cost tracking.

---

## 4. Using the Pipeline

### Trigger a run

```bash
# Via CLI (inside the worker container)
docker compose exec worker rak run --config /app/rak-config.yaml

# Via API (from your host machine)
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"regulation_id": "dora-ict-risk-2025", "change_type": "new_requirement"}'
```

### Check pipeline status

```bash
docker compose exec worker rak status --run-id <uuid>
```

Example output:

```
Run:    a1b2c3d4-e5f6-7890-abcd-ef1234567890
Status: running
Phase:  AWAITING_IMPACT_REVIEW (waiting for human approval)
Repos:  3 total
  - 1 completed
  - 1 in_progress
  - 1 pending
Cost:   $0.82 estimated / $0.31 actual
```

Or visit the **Temporal UI** at [http://localhost:8080](http://localhost:8080) to see the workflow visually.

### Approve checkpoints

When `checkpoint_mode: terminal`:

```bash
# The worker container will prompt you interactively
docker compose attach worker
# Follow the prompts to approve/reject the impact assessment or merge review
```

When `checkpoint_mode: slack` or `email`, approvals arrive as notifications with an approval link pointing to the RAK API (`localhost:8000`).

### Retry failed repositories

```bash
docker compose exec worker rak retry-failures --run-id <uuid>
```

### Rollback a pipeline run

```bash
docker compose exec worker rak rollback --run-id <uuid>
```

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f worker
docker compose logs -f temporal-server
```

---

## 5. Stopping and Cleaning Up

```bash
# Stop all services (preserves data)
docker compose down

# Stop and delete all data (databases, indexes, volumes)
docker compose down -v

# Restart a single service
docker compose restart worker
```

Database data is persisted in Docker volumes. A `docker compose down` (without `-v`) preserves your pipeline history, audit trail, and MLflow traces between restarts.

---

## 6. Troubleshooting

### Services fail to start

| Symptom | Cause | Fix |
|---|---|---|
| `elasticsearch` exits with code 137 | Out of memory (Elasticsearch needs ~2 GB) | Increase Docker memory to 12+ GB in Docker Desktop settings |
| `temporal-server` restarts repeatedly | PostgreSQL not ready yet | Wait 30 seconds and check again — Temporal retries automatically |
| `worker` exits with `ANTHROPIC_API_KEY not set` | Missing `.env` file or empty key | Verify `.env` exists and contains a valid API key |
| Port conflict on 5432, 8080, 9200, etc. | Another service using the port | Stop the conflicting service, or override ports in `docker-compose.override.yml` |

### Pipeline issues

| Symptom | Cause | Fix |
|---|---|---|
| `rak run` hangs at "Waiting for Temporal..." | Temporal server not fully initialized | Check `docker compose ps` — wait for `temporal-server` to be healthy |
| Repository clone fails | Private repo without token | Add `GITHUB_TOKEN` or `GITLAB_TOKEN` to `.env` |
| LLM calls fail with 401 | Invalid or expired API key | Verify your key at [console.anthropic.com](https://console.anthropic.com/) and update `.env` |
| Cost estimate too high | Large repo count or complex regulation | Reduce `repos` list or increase `cost_threshold` in `rak-config.yaml` |
| Elasticsearch `yellow` status | Single-node cluster (expected in dev) | This is normal for local development — no action needed |

### Reset everything

```bash
# Nuclear option — removes all containers, volumes, and images
docker compose down -v --rmi local
docker compose up -d
```

---

## 7. Next Steps

| Your goal | Read next |
|---|---|
| Write a custom regulation plugin | [`plugin-template-guide.md`](plugin-template-guide.md) |
| Understand the pipeline architecture | [`architecture.md`](architecture.md) |
| Deploy to production (Kubernetes) | [`infrastructure.md`](infrastructure.md) |
| Operate and troubleshoot in production | [`operations/runbook.md`](operations/runbook.md) |
| Look up a CLI command | [`cli-reference.md`](cli-reference.md) |

---

*See also: [`getting-started.md`](getting-started.md) for Lite Mode (no Docker required), [`infrastructure.md`](infrastructure.md) for production deployment, and [`hld.md`](hld.md) for the full system design.*
