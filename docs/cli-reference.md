# CLI Reference

**Framework:** Typer (see [ADR-004](adr/004-python-stack.md))
**Entry point:** `python -m regulatory_agent_kit.cli` or `rak` (after `pip install`)

---

## Pipeline Commands

### `rak run`

Run a compliance pipeline against one or more repositories.

```bash
rak run \
  --regulation <path-to-plugin.yaml> \
  --repos <repo-url-or-path> [<repo-url-or-path> ...] \
  --checkpoint-mode <terminal|slack|email|webhook> \
  [--slack-channel <channel>] \
  [--lite]
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--regulation` | Yes | — | Path to regulation plugin YAML file |
| `--repos` | Yes | — | One or more repository URLs (HTTPS) or local paths |
| `--checkpoint-mode` | Yes | — | How human approvals are collected: `terminal` (interactive), `slack`, `email`, `webhook` |
| `--slack-channel` | No | — | Slack channel for approvals (required if `--checkpoint-mode slack`) |
| `--lite` | No | `false` | Run in Lite Mode: no Temporal, no Elasticsearch, SQLite, sequential processing. See [`infrastructure.md` Section 8.5](infrastructure.md) |

**Examples:**

```bash
# Lite mode evaluation (< 5 minutes, no infrastructure)
export ANTHROPIC_API_KEY=your_key
rak run --lite \
  --regulation regulations/examples/example.yaml \
  --repos ./my-local-repo \
  --checkpoint-mode terminal

# Full mode with Slack approvals
rak run \
  --regulation regulations/dora/dora-ict-risk-2025.yaml \
  --repos https://github.com/org/service-a \
           https://github.com/org/service-b \
  --checkpoint-mode slack \
  --slack-channel "#compliance-approvals"
```

### `rak status`

Check the status of a pipeline run.

```bash
rak status --run-id <uuid> [--filter <pending|in_progress|completed|failed|skipped>]
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--run-id` | Yes | — | Pipeline run UUID |
| `--filter` | No | — | Filter repositories by status |

**Output:** Summary of pipeline state, per-repository progress, cost tracking, and checkpoint decisions.

### `rak retry-failures`

Retry only the failed repositories from a previous run. Successful repositories are not re-processed.

```bash
rak retry-failures --run-id <uuid>
```

In Temporal mode, this re-signals the failed child workflows. In Lite Mode, this command is not available.

### `rak rollback`

Reverse all changes from a pipeline run using the stored rollback manifest.

```bash
rak rollback --run-id <uuid>
```

**Actions performed:**
1. Closes open pull requests created by the run
2. Deletes branches created by the run
3. Creates revert PRs for any changes that were already merged

### `rak resume`

Resume a pipeline that was interrupted (e.g., process crash in Lite Mode).

```bash
rak resume --run-id <uuid>
```

In Temporal mode, workflows auto-recover — this command is rarely needed. In Lite Mode, it re-reads the SQLite state and continues from the last completed step.

---

## Plugin Commands

### `rak plugin init`

Scaffold a new regulation plugin with boilerplate YAML, Jinja2 templates, test fixtures, and README.

```bash
rak plugin init --name <plugin-name>
```

**Output:** Creates `regulations/<plugin-name>/` with:
- `<plugin-name>.yaml` — Plugin YAML with required fields pre-populated
- `templates/` — Jinja2 template stubs for each remediation strategy
- `tests/` — Test fixture directory with synthetic repository structure
- `README.md` — Plugin documentation template

### `rak plugin validate`

Validate a plugin YAML file against the schema, verify template files exist and render, and check test fixtures.

```bash
rak plugin validate <path-to-plugin.yaml>
```

**Checks performed:**
1. YAML schema validation (all required fields present, correct types)
2. `disclaimer` field is non-empty
3. All referenced `template` and `test_template` paths exist
4. Templates render without errors against a synthetic context
5. Condition DSL expressions parse without errors
6. `cross_references` reference valid relationship and conflict_handling values

### `rak plugin test`

Run a plugin against a test repository to verify rule matching and remediation.

```bash
rak plugin test <path-to-plugin.yaml> --repo <path-to-test-repo>
```

Executes the Analyzer Agent against the test repository using the plugin, reports which rules matched, and optionally applies remediations to verify template output.

### `rak plugin search`

Search the plugin registry for community and official plugins.

```bash
rak plugin search <query>
```

Queries the plugin registry (GitHub-based YAML index) by keyword, regulation name, or jurisdiction.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (if using Anthropic) | — | Anthropic API key for Claude models |
| `OPENAI_API_KEY` | No | — | OpenAI API key (for fallback routing via LiteLLM) |
| `DATABASE_URL` | No (Lite: SQLite) | `sqlite:///rak.db` | PostgreSQL connection string for full mode |
| `ELASTICSEARCH_URL` | No | — | Elasticsearch endpoint URL |
| `MLFLOW_TRACKING_URI` | No | — | MLflow tracking server URL (if not set, traces go to stdout) |
| `KAFKA_BOOTSTRAP_SERVERS` | No | — | Kafka broker addresses (for KafkaEventSource) |
| `RAK_CACHE_TTL_DAYS` | No | `7` | File analysis cache expiration in days |
