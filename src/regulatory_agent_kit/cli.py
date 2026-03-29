"""CLI entry point for regulatory-agent-kit.

Provides the ``rak`` command with subcommands for running compliance pipelines,
managing pipeline state, validating regulation plugins, and database maintenance.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from regulatory_agent_kit.config import Settings, load_settings
from regulatory_agent_kit.exceptions import (
    PluginLoadError,
    PluginValidationError,
)
from regulatory_agent_kit.plugins.loader import PluginLoader
from regulatory_agent_kit.plugins.scaffolder import PluginScaffolder

logger = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# Top-level app
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="rak",
    help="regulatory-agent-kit — AI-powered regulatory compliance automation",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Sub-groups: plugin, db
# ---------------------------------------------------------------------------

plugin_app = typer.Typer(
    name="plugin",
    help="Manage regulation plugins.",
    no_args_is_help=True,
)
app.add_typer(plugin_app, name="plugin")

db_app = typer.Typer(
    name="db",
    help="Database maintenance commands.",
    no_args_is_help=True,
)
app.add_typer(db_app, name="db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_uuid(value: str) -> str:
    """Validate that a string is a valid UUID."""
    try:
        UUID(value)
    except ValueError:
        msg = f"Invalid UUID: {value}"
        raise typer.BadParameter(msg) from None
    return value


def _lite_db_path(settings: Settings) -> Path:
    """Return the SQLite database path for Lite Mode."""
    return Path.home() / ".rak" / "lite.db"


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from synchronous CLI context."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# rak run
# ---------------------------------------------------------------------------


@app.command()
def run(
    regulation: Annotated[
        str,
        typer.Option(help="Path to regulation plugin YAML."),
    ],
    repos: Annotated[
        list[str],
        typer.Option(help="Repository URLs or local paths to analyze."),
    ],
    checkpoint_mode: Annotated[
        str,
        typer.Option(help="Approval mode: terminal|slack|email|webhook."),
    ] = "terminal",
    lite: Annotated[
        bool,
        typer.Option(help="Run in Lite Mode (no external services)."),
    ] = False,
    config: Annotated[
        str | None,
        typer.Option(help="Path to rak-config.yaml for pipeline configuration."),
    ] = None,
) -> None:
    """Run the compliance pipeline against target repositories."""
    overrides: dict[str, object] = {}
    if lite:
        overrides["lite_mode"] = True
    if checkpoint_mode != "terminal":
        overrides["checkpoint_mode"] = checkpoint_mode

    settings = load_settings(
        yaml_path=config,
        overrides=overrides,
    )

    plugin_path = Path(regulation)
    loader = PluginLoader()
    try:
        plugin = loader.load(plugin_path)
    except (PluginLoadError, PluginValidationError) as exc:
        console.print(f"[red]Error loading plugin:[/red] {exc}")
        raise typer.Exit(code=1) from None

    mode = "Lite Mode" if settings.lite_mode else "Temporal"
    console.print(f"[bold green]Pipeline starting[/bold green] ({mode})")
    console.print(f"  Regulation : {plugin.name} ({plugin.id})")
    console.print(f"  Repos      : {', '.join(repos)}")
    console.print(f"  Checkpoint : {settings.checkpoint_mode}")

    if settings.lite_mode:
        _run_lite_pipeline(plugin, repos, settings)
    else:
        _run_temporal_pipeline(plugin, repos, settings)


def _run_lite_pipeline(
    plugin: Any,
    repos: list[str],
    settings: Settings,
) -> None:
    """Execute the pipeline using the Lite Mode sequential executor."""
    from regulatory_agent_kit.orchestration.lite import LiteModeExecutor

    executor = LiteModeExecutor(db_path=_lite_db_path(settings))
    result = _run_async(
        executor.run(
            regulation_id=plugin.id,
            repo_urls=repos,
            plugin_data=plugin.model_dump(mode="json"),
            config={
                "default_model": settings.llm.default_model,
                "cost_threshold": settings.cost_threshold,
                "auto_approve_cost": settings.auto_approve_cost,
                "checkpoint_mode": settings.checkpoint_mode,
                "max_retries": settings.max_retries,
            },
        )
    )

    console.print()
    console.print(f"[bold]Run ID:[/bold] {result.run_id}")
    console.print(f"[bold]Status:[/bold] {result.status}")
    console.print(f"[bold]Phases:[/bold] {' → '.join(result.phases_executed)}")

    if result.cost_estimate:
        cost = result.cost_estimate.get("estimated_total_cost", 0)
        console.print(f"[bold]Est. cost:[/bold] ${cost:.4f}")

    console.print(f"[bold]Repos processed:[/bold] {len(result.repo_results)}")
    console.print("[green]Pipeline completed.[/green]")


def _run_temporal_pipeline(
    plugin: Any,
    repos: list[str],
    settings: Settings,
) -> None:
    """Start the pipeline as a Temporal workflow."""

    async def _start() -> str:
        from temporalio.client import Client

        from regulatory_agent_kit.event_sources.starter import WorkflowStarter
        from regulatory_agent_kit.models.events import RegulatoryEvent

        client = await Client.connect(settings.temporal.address)
        starter = WorkflowStarter(client, task_queue=settings.temporal.task_queue)

        event = RegulatoryEvent(
            regulation_id=plugin.id,
            change_type="new_requirement",
            source="cli",
            payload={},
        )
        workflow_id = await starter.start_pipeline(
            event=event,
            plugin=plugin.model_dump(mode="json"),
            config={
                "default_model": settings.llm.default_model,
                "cost_threshold": settings.cost_threshold,
                "auto_approve_cost": settings.auto_approve_cost,
                "checkpoint_mode": settings.checkpoint_mode,
                "max_retries": settings.max_retries,
                "repo_urls": repos,
            },
        )
        return workflow_id

    try:
        workflow_id = _run_async(_start())
    except Exception as exc:
        console.print(f"[red]Failed to start Temporal workflow:[/red] {exc}")
        raise typer.Exit(code=1) from None

    console.print(f"[bold]Workflow ID:[/bold] {workflow_id}")
    console.print("[green]Pipeline dispatched to Temporal.[/green]")
    console.print("Use [bold]rak status[/bold] to track progress.")


# ---------------------------------------------------------------------------
# rak status
# ---------------------------------------------------------------------------


@app.command()
def status(
    run_id: Annotated[
        str,
        typer.Option(help="Pipeline run ID (UUID)."),
    ],
    filter: Annotated[
        str | None,
        typer.Option(help="Filter repos by status: pending|in_progress|completed|failed|skipped."),
    ] = None,
) -> None:
    """Query and display pipeline run status."""
    run_id = _validate_uuid(run_id)

    run_data = _run_async(_query_lite_status(run_id))
    if run_data is None:
        console.print(f"[yellow]No pipeline run found with ID {run_id}.[/yellow]")
        console.print("If using Temporal mode, the run is tracked in Temporal, not SQLite.")
        raise typer.Exit(code=1)

    run_info, repos = run_data

    table = Table(title=f"Pipeline Status: {run_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Run ID", run_id)
    table.add_row("Regulation", run_info.get("regulation_id", "—"))
    table.add_row("Status", run_info.get("status", "unknown"))
    table.add_row("Created", run_info.get("created_at", "—"))
    table.add_row("Repos", str(run_info.get("total_repos", len(repos))))

    est_cost = run_info.get("estimated_cost")
    actual_cost = run_info.get("actual_cost")
    cost_str = ""
    if est_cost is not None:
        cost_str += f"${float(est_cost):.4f} estimated"
    if actual_cost is not None:
        if cost_str:
            cost_str += " / "
        cost_str += f"${float(actual_cost):.4f} actual"
    table.add_row("Cost", cost_str or "—")
    console.print(table)

    if repos:
        repo_table = Table(title="Repository Progress")
        repo_table.add_column("Repository", style="white")
        repo_table.add_column("Status", style="cyan")
        repo_table.add_column("Error", style="red")

        for repo in repos:
            repo_status = repo.get("status", "unknown")
            if filter and repo_status != filter:
                continue
            repo_table.add_row(
                repo.get("repo_url", "—"),
                repo_status,
                repo.get("error", "") or "",
            )
        console.print(repo_table)


async def _query_lite_status(
    run_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """Query a Lite Mode SQLite database for pipeline run status."""
    from regulatory_agent_kit.database.lite import (
        LitePipelineRunRepository,
        LiteRepositoryProgressRepository,
    )

    db_path = Path.home() / ".rak" / "lite.db"
    if not db_path.exists():
        return None

    run_uuid = UUID(run_id)
    pipeline_repo = LitePipelineRunRepository(db_path)
    progress_repo = LiteRepositoryProgressRepository(db_path)

    run_info = await pipeline_repo.get(run_uuid)
    if run_info is None:
        return None

    repos = await progress_repo.get_by_run(run_uuid)
    return run_info, repos


# ---------------------------------------------------------------------------
# rak retry-failures
# ---------------------------------------------------------------------------


@app.command(name="retry-failures")
def retry_failures(
    run_id: Annotated[
        str,
        typer.Option(help="Pipeline run ID (UUID) to retry failed repos."),
    ],
) -> None:
    """Find failed repos in a pipeline run and trigger re-dispatch."""
    run_id = _validate_uuid(run_id)
    console.print(f"Retrying failures for run: {run_id}")

    failed = _run_async(_get_failed_repos(run_id))
    if failed is None:
        console.print("[yellow]Run not found in Lite Mode database.[/yellow]")
        raise typer.Exit(code=1)

    if not failed:
        console.print("[green]No failed repositories to retry.[/green]")
        return

    console.print(f"Found {len(failed)} failed repo(s):")
    for repo in failed:
        console.print(f"  - {repo.get('repo_url', '—')}: {repo.get('error', 'unknown error')}")
    console.print(
        "[yellow]Re-dispatch is not yet available — "
        "failed repos have been identified for manual retry.[/yellow]"
    )


async def _get_failed_repos(run_id: str) -> list[dict[str, Any]] | None:
    """Query failed repositories from Lite Mode SQLite."""
    from regulatory_agent_kit.database.lite import (
        LitePipelineRunRepository,
        LiteRepositoryProgressRepository,
    )

    db_path = Path.home() / ".rak" / "lite.db"
    if not db_path.exists():
        return None

    run_uuid = UUID(run_id)
    pipeline_repo = LitePipelineRunRepository(db_path)
    progress_repo = LiteRepositoryProgressRepository(db_path)

    run_info = await pipeline_repo.get(run_uuid)
    if run_info is None:
        return None

    all_repos = await progress_repo.get_by_run(run_uuid)
    return [r for r in all_repos if r.get("status") == "failed"]


# ---------------------------------------------------------------------------
# rak rollback
# ---------------------------------------------------------------------------


@app.command()
def rollback(
    run_id: Annotated[
        str,
        typer.Option(help="Pipeline run ID (UUID) to rollback."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview rollback without executing."),
    ] = False,
) -> None:
    """Read rollback manifest and preview or execute cleanup."""
    run_id = _validate_uuid(run_id)
    manifest = _run_async(_load_rollback_manifest(run_id))
    if manifest is None:
        console.print(f"[yellow]No rollback manifest found for run {run_id}.[/yellow]")
        raise typer.Exit(code=1)

    repos = manifest.get("repos", [])
    if not repos:
        console.print("[green]No repositories to rollback.[/green]")
        return

    prefix = "[DRY RUN] " if dry_run else ""
    console.print(f"{prefix}Rolling back run: {run_id}")
    console.print(f"{prefix}Repositories affected: {len(repos)}")

    table = Table(title=f"{prefix}Rollback Actions")
    table.add_column("Repository", style="white")
    table.add_column("Branch", style="cyan")
    table.add_column("PR", style="blue")
    table.add_column("Action", style="yellow")

    for repo in repos:
        pr_state = repo.get("pr_state", "unknown")
        if pr_state == "merged":
            action = "Create revert PR"
        elif pr_state == "open":
            action = "Close PR + delete branch"
        else:
            action = "Delete branch"

        table.add_row(
            repo.get("repo_url", "—"),
            repo.get("branch_name", "—"),
            repo.get("pr_url", "—"),
            action,
        )
    console.print(table)

    if dry_run:
        console.print("[yellow]Dry run — no actions taken.[/yellow]")
    else:
        console.print(
            "[yellow]Rollback execution requires Git provider integration "
            "(not yet available in Lite Mode).[/yellow]"
        )


async def _load_rollback_manifest(run_id: str) -> dict[str, Any] | None:
    """Load the rollback manifest from the audit trail or local file."""
    manifest_path = Path(f"/tmp/rak/{run_id}/rollback.yaml")  # noqa: S108
    if manifest_path.exists():
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        data: dict[str, Any] = yaml.load(manifest_path)
        return data

    jsonl_path = Path.home() / ".rak" / "lite.db"
    if not jsonl_path.exists():
        return None

    from regulatory_agent_kit.database.lite import LiteAuditRepository

    audit_repo = LiteAuditRepository(jsonl_path)
    entries = await audit_repo.get_by_run(UUID(run_id))
    for entry in entries:
        payload_raw = entry.get("payload", "{}")
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        is_manifest = payload.get("@type") == "RollbackManifest"
        is_merge_req = entry.get("event_type") == "merge_request"
        if is_manifest or is_merge_req:
            return payload

    return {"run_id": run_id, "repos": []}


# ---------------------------------------------------------------------------
# rak resume
# ---------------------------------------------------------------------------


@app.command()
def resume(
    run_id: Annotated[
        str,
        typer.Option(help="Pipeline run ID (UUID) to resume."),
    ],
) -> None:
    """Resume an interrupted Lite Mode pipeline from its last checkpoint."""
    run_id = _validate_uuid(run_id)
    console.print(f"Resuming run: {run_id}")

    result = _run_async(_resume_lite_run(run_id))
    if result is None:
        console.print(f"[yellow]Run {run_id} not found in Lite Mode database.[/yellow]")
        raise typer.Exit(code=1)

    run_status = result.get("status", "unknown")
    if run_status in ("completed", "failed", "rejected", "cost_rejected", "cancelled"):
        console.print(
            f"[yellow]Run is already in terminal state: {run_status}. Cannot resume.[/yellow]"
        )
        return

    console.print(f"[bold]Current status:[/bold] {run_status}")
    console.print(
        "[yellow]Lite Mode resume re-reads SQLite state and continues from last phase. "
        "Full resume logic requires the WAL replay integration.[/yellow]"
    )


async def _resume_lite_run(run_id: str) -> dict[str, Any] | None:
    """Query Lite Mode SQLite for a run to resume."""
    from regulatory_agent_kit.database.lite import LitePipelineRunRepository

    db_path = Path.home() / ".rak" / "lite.db"
    if not db_path.exists():
        return None

    pipeline_repo = LitePipelineRunRepository(db_path)
    return await pipeline_repo.get(UUID(run_id))


# ---------------------------------------------------------------------------
# rak cancel
# ---------------------------------------------------------------------------


@app.command()
def cancel(
    run_id: Annotated[
        str,
        typer.Option(help="Pipeline run ID (UUID) to cancel."),
    ],
) -> None:
    """Cancel a running pipeline."""
    run_id = _validate_uuid(run_id)
    console.print(f"Cancelling run: {run_id}")

    result = _run_async(_cancel_run(run_id))
    if result == "not_found":
        console.print(f"[yellow]Run {run_id} not found.[/yellow]")
        raise typer.Exit(code=1)
    elif result == "already_terminal":
        console.print("[yellow]Run is already in a terminal state.[/yellow]")
    else:
        console.print(f"[green]Run {run_id} marked as cancelled.[/green]")


async def _cancel_run(run_id: str) -> str:
    """Cancel a Lite Mode run by updating its status."""
    from regulatory_agent_kit.database.lite import LitePipelineRunRepository

    db_path = Path.home() / ".rak" / "lite.db"
    if not db_path.exists():
        return "not_found"

    pipeline_repo = LitePipelineRunRepository(db_path)
    run_info = await pipeline_repo.get(UUID(run_id))
    if run_info is None:
        return "not_found"

    current_status = run_info.get("status", "")
    if current_status in ("completed", "failed", "rejected", "cost_rejected", "cancelled"):
        return "already_terminal"

    await pipeline_repo.update_status(UUID(run_id), "cancelled")
    return "cancelled"


# ---------------------------------------------------------------------------
# rak plugin validate
# ---------------------------------------------------------------------------


@plugin_app.command(name="validate")
def plugin_validate(
    path: Annotated[
        str,
        typer.Argument(help="Path to regulation plugin YAML file."),
    ],
) -> None:
    """Validate a regulation plugin YAML file against the schema."""
    plugin_path = Path(path)
    loader = PluginLoader()
    errors = loader.validate(plugin_path)
    if errors:
        console.print(f"[red]Validation failed for {path}:[/red]")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(code=1)
    console.print(f"[green]Plugin {path} is valid.[/green]")


# ---------------------------------------------------------------------------
# rak plugin init
# ---------------------------------------------------------------------------


@plugin_app.command(name="init")
def plugin_init(
    name: Annotated[
        str,
        typer.Option(help="Name for the new regulation plugin."),
    ],
    output_dir: Annotated[
        str,
        typer.Option(help="Parent directory for the plugin scaffold."),
    ] = "regulations",
) -> None:
    """Scaffold a new regulation plugin directory structure."""
    scaffolder = PluginScaffolder()
    try:
        plugin_dir = scaffolder.scaffold(name, Path(output_dir))
    except FileExistsError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None
    console.print(f"[green]Plugin scaffold created at {plugin_dir}[/green]")


# ---------------------------------------------------------------------------
# rak plugin test
# ---------------------------------------------------------------------------


@plugin_app.command(name="test")
def plugin_test(
    path: Annotated[
        str,
        typer.Argument(help="Path to regulation plugin YAML file."),
    ],
    repo: Annotated[
        str,
        typer.Option(help="Path to test repository directory."),
    ] = ".",
) -> None:
    """Run a regulation plugin against a test repository to verify rule matching."""
    plugin_path = Path(path)
    repo_path = Path(repo)

    loader = PluginLoader()
    try:
        plugin = loader.load(plugin_path)
    except (PluginLoadError, PluginValidationError) as exc:
        console.print(f"[red]Error loading plugin:[/red] {exc}")
        raise typer.Exit(code=1) from None

    if not repo_path.is_dir():
        console.print(f"[red]Repository path is not a directory: {repo_path}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Testing plugin:[/bold] {plugin.name} ({plugin.id})")
    console.print(f"[bold]Against repo:[/bold]  {repo_path.resolve()}")
    console.print()

    total_matches = 0
    for rule in plugin.rules:
        matches: list[str] = []
        for affects in rule.affects:
            matched_files = list(repo_path.glob(affects.pattern))
            matches.extend(str(f.relative_to(repo_path)) for f in matched_files)

        if matches:
            total_matches += len(matches)
            console.print(
                f"  [cyan]{rule.id}[/cyan] ({rule.severity}): "
                f"{len(matches)} file(s) matched"
            )
            for m in matches[:5]:
                console.print(f"    - {m}")
            if len(matches) > 5:
                console.print(f"    ... and {len(matches) - 5} more")
        else:
            console.print(f"  [dim]{rule.id}[/dim] ({rule.severity}): no matches")

    console.print()
    console.print(
        f"[bold]Summary:[/bold] {total_matches} file(s) matched "
        f"across {len(plugin.rules)} rule(s)"
    )


# ---------------------------------------------------------------------------
# rak plugin search
# ---------------------------------------------------------------------------


@plugin_app.command(name="search")
def plugin_search(
    query: Annotated[
        str,
        typer.Argument(help="Search term (name, jurisdiction, or keyword)."),
    ],
    plugin_dir: Annotated[
        str,
        typer.Option(help="Directory to search for plugins."),
    ] = "regulations",
) -> None:
    """Search local regulation plugins by keyword."""
    search_path = Path(plugin_dir)
    if not search_path.is_dir():
        console.print(f"[yellow]Plugin directory not found: {search_path}[/yellow]")
        raise typer.Exit(code=1)

    loader = PluginLoader(plugin_dir=search_path)
    query_lower = query.lower()
    results: list[Any] = []

    for yaml_file in search_path.rglob("*.yaml"):
        try:
            plugin = loader.load(yaml_file)
        except (PluginLoadError, PluginValidationError):
            continue

        searchable = " ".join([
            plugin.id,
            plugin.name,
            plugin.jurisdiction,
            plugin.authority,
            plugin.version,
        ]).lower()

        if query_lower in searchable:
            results.append(plugin)

    if not results:
        console.print(f"[yellow]No plugins found matching '{query}'.[/yellow]")
        return

    table = Table(title=f"Plugins matching '{query}'")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Version", style="dim")
    table.add_column("Jurisdiction", style="green")

    for p in results:
        table.add_row(p.id, p.name, p.version, p.jurisdiction)
    console.print(table)


# ---------------------------------------------------------------------------
# rak db clean-cache
# ---------------------------------------------------------------------------


@db_app.command(name="clean-cache")
def db_clean_cache() -> None:
    """Invoke cache cleanup on the file analysis cache."""
    console.print("Cleaning analysis cache...")
    deleted = _run_async(_clean_cache())
    if deleted is None:
        console.print(
            "[yellow]Cache cleanup requires PostgreSQL "
            "(not available in Lite Mode).[/yellow]"
        )
    elif deleted == 0:
        console.print("[green]No expired cache entries found.[/green]")
    else:
        console.print(f"[green]Deleted {deleted} expired cache entries.[/green]")


async def _clean_cache() -> int | None:
    """Delete expired file analysis cache entries from PostgreSQL."""
    try:
        from regulatory_agent_kit.database.pool import get_pool

        pool = get_pool()
    except RuntimeError:
        return None

    from regulatory_agent_kit.database.repositories.file_analysis_cache import (
        FileAnalysisCacheRepository,
    )

    async with pool.connection() as conn:
        repo = FileAnalysisCacheRepository(conn)
        return await repo.delete_expired()


# ---------------------------------------------------------------------------
# rak db create-partitions
# ---------------------------------------------------------------------------


@db_app.command(name="create-partitions")
def db_create_partitions(
    months: Annotated[
        int,
        typer.Option(help="Number of months of audit partitions to create."),
    ] = 3,
) -> None:
    """Create the next N months of audit_entries table partitions."""
    console.print(f"Creating {months} month(s) of audit partitions...")
    created = _run_async(_create_partitions(months))
    if created is None:
        console.print(
            "[yellow]Partition creation requires PostgreSQL "
            "(not available in Lite Mode).[/yellow]"
        )
    elif not created:
        console.print("[green]All partitions already exist.[/green]")
    else:
        for name in created:
            console.print(f"  [green]Created:[/green] {name}")


async def _create_partitions(months: int) -> list[str] | None:
    """Create monthly range partitions for rak.audit_entries."""
    try:
        from regulatory_agent_kit.database.pool import get_pool

        pool = get_pool()
    except RuntimeError:
        return None

    now = datetime.now(UTC)
    created: list[str] = []

    async with pool.connection() as conn:
        for offset in range(months):
            month = now.month + offset
            year = now.year
            while month > 12:
                month -= 12
                year += 1
            next_month = month + 1
            next_year = year
            if next_month > 12:
                next_month = 1
                next_year += 1

            partition_name = f"audit_entries_y{year}m{month:02d}"
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{next_year}-{next_month:02d}-01"

            try:
                await conn.execute(
                    f"CREATE TABLE IF NOT EXISTS rak.{partition_name} "
                    f"PARTITION OF rak.audit_entries "
                    f"FOR VALUES FROM ('{start_date}') TO ('{end_date}')"
                )
                created.append(partition_name)
            except Exception:
                logger.debug("Partition %s may already exist", partition_name, exc_info=True)

    return created


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
