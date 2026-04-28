"""CLI entry point for regulatory-agent-kit.

Provides the ``rak`` command with subcommands for running compliance pipelines,
managing pipeline state, validating regulation plugins, and database maintenance.
"""

from __future__ import annotations

import asyncio
import json
import logging
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
from regulatory_agent_kit.models.pipeline import TERMINAL_STATUSES
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

ci_app = typer.Typer(
    name="ci",
    help="CI/CD compliance analysis commands.",
    no_args_is_help=True,
)
app.add_typer(ci_app, name="ci")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_LITE_DB_PATH = Path.home() / ".rak" / "lite.db"
"""Default SQLite database path for Lite Mode — single source of truth."""


def _validate_uuid(value: str) -> str:
    """Validate that a string is a valid UUID."""
    try:
        UUID(value)
    except ValueError:
        msg = f"Invalid UUID: {value}"
        raise typer.BadParameter(msg) from None
    return value


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from synchronous CLI context."""
    return asyncio.run(coro)


async def _get_lite_run(run_id: str) -> dict[str, Any] | None:
    """Fetch a pipeline run from Lite Mode SQLite, or None if missing."""
    from regulatory_agent_kit.database.lite import LitePipelineRunRepository

    if not _LITE_DB_PATH.exists():
        return None
    return await LitePipelineRunRepository(_LITE_DB_PATH).get(UUID(run_id))


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

    executor = LiteModeExecutor(db_path=_LITE_DB_PATH)
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
    from regulatory_agent_kit.database.lite import LiteRepositoryProgressRepository

    run_info = await _get_lite_run(run_id)
    if run_info is None:
        return None

    progress_repo = LiteRepositoryProgressRepository(_LITE_DB_PATH)
    repos = await progress_repo.get_by_run(UUID(run_id))
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
    """Re-dispatch failed repositories from a pipeline run."""
    run_id = _validate_uuid(run_id)
    console.print(f"Retrying failures for run: {run_id}")

    result = _run_async(_retry_failed_repos(run_id))
    if result is None:
        console.print("[yellow]Run not found in Lite Mode database.[/yellow]")
        raise typer.Exit(code=1)

    if not result["failed_repos"]:
        console.print("[green]No failed repositories to retry.[/green]")
        return

    console.print(f"Re-dispatching {len(result['failed_repos'])} failed repo(s)...")
    console.print(f"[bold]New run ID:[/bold] {result['new_run_id']}")
    console.print(f"[bold]Status:[/bold] {result['status']}")


async def _get_failed_repos(run_id: str) -> list[dict[str, Any]] | None:
    """Query failed repositories from Lite Mode SQLite."""
    from regulatory_agent_kit.database.lite import LiteRepositoryProgressRepository

    run_info = await _get_lite_run(run_id)
    if run_info is None:
        return None

    all_repos = await LiteRepositoryProgressRepository(_LITE_DB_PATH).get_by_run(UUID(run_id))
    return [r for r in all_repos if r.get("status") == "failed"]


async def _retry_failed_repos(run_id: str) -> dict[str, Any] | None:
    """Identify failed repos and re-dispatch them through the LiteModeExecutor."""
    from regulatory_agent_kit.database.lite import LitePipelineRunRepository
    from regulatory_agent_kit.orchestration.lite import LiteModeExecutor

    failed = await _get_failed_repos(run_id)
    if failed is None:
        return None

    failed_urls = [r["repo_url"] for r in failed if r.get("status") == "failed"]
    if not failed_urls:
        return {"failed_repos": [], "new_run_id": "", "status": "no_failures"}

    # Get original run config
    run_data = await LitePipelineRunRepository(_LITE_DB_PATH).get(UUID(run_id))
    if run_data is None:
        return None

    config_raw = run_data.get("config_snapshot", "{}")
    config = json.loads(config_raw) if isinstance(config_raw, str) else config_raw
    regulation_id = run_data.get("regulation_id", "")

    # Re-run with failed repos only
    executor = LiteModeExecutor(db_path=_LITE_DB_PATH)
    result = await executor.run(
        regulation_id=regulation_id,
        repo_urls=failed_urls,
        plugin_data=config.get("plugin_data", {}),
        config=config,
    )

    return {
        "failed_repos": failed_urls,
        "new_run_id": result.run_id,
        "status": result.status,
    }


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
    from regulatory_agent_kit.tools.rollback import (
        RollbackExecutor,
        plan_rollback,
    )

    run_id = _validate_uuid(run_id)
    manifest = _run_async(_load_rollback_manifest(run_id))
    if manifest is None:
        console.print(f"[yellow]No rollback manifest found for run {run_id}.[/yellow]")
        raise typer.Exit(code=1)

    actions = plan_rollback(manifest)
    if not actions:
        console.print("[green]No repositories to rollback.[/green]")
        return

    prefix = "[DRY RUN] " if dry_run else ""
    console.print(f"{prefix}Rolling back run: {run_id}")
    console.print(f"{prefix}Repositories affected: {len(actions)}")

    table = Table(title=f"{prefix}Rollback Actions")
    table.add_column("Repository", style="white")
    table.add_column("Branch", style="cyan")
    table.add_column("PR", style="blue")
    table.add_column("PR State", style="dim")
    table.add_column("Action", style="yellow")

    action_labels = {
        "close_pr_and_delete_branch": "Close PR + delete branch",
        "create_revert_pr": "Create revert PR",
        "delete_branch": "Delete branch",
        "skip": "Skip (already closed)",
    }

    for action in actions:
        table.add_row(
            action.repo_url or "—",
            action.branch_name or "—",
            action.pr_url or "—",
            action.pr_state,
            action_labels.get(action.action, action.action),
        )
    console.print(table)

    executor = RollbackExecutor()
    results = _run_async(executor.execute(actions, dry_run=dry_run))

    success_count = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success)

    for r in results:
        if r.success:
            console.print(f"  [green]{r.repo_url}:[/green] {r.detail}")
        elif r.error:
            console.print(f"  [red]{r.repo_url}:[/red] {r.error}")

    if dry_run:
        console.print("[yellow]Dry run — no actions executed.[/yellow]")
    else:
        console.print(
            f"[bold]Rollback complete:[/bold] "
            f"{success_count} succeeded, {fail_count} failed"
        )


async def _load_rollback_manifest(run_id: str) -> dict[str, Any] | None:
    """Load the rollback manifest from filesystem or audit trail."""
    from regulatory_agent_kit.tools.rollback import (
        load_manifest_from_audit_trail,
        load_manifest_from_file,
    )

    # Check compliance-reports directory (written by ComplianceReportGenerator)
    report_manifest = Path("compliance-reports") / run_id / "rollback-manifest.json"
    loaded = load_manifest_from_file(report_manifest)
    if loaded is not None:
        return loaded

    # Check legacy /tmp path
    tmp_manifest = Path(f"/tmp/rak/{run_id}/rollback-manifest.json")  # noqa: S108
    loaded = load_manifest_from_file(tmp_manifest)
    if loaded is not None:
        return loaded

    # Search Lite Mode audit trail
    loaded = await load_manifest_from_audit_trail(run_id, _LITE_DB_PATH)
    if loaded is not None:
        return loaded

    return None


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

    if result.get("error"):
        console.print(f"[yellow]Cannot resume: {result['error']}[/yellow]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Resumed run:[/bold] {run_id}")
    console.print(f"[bold]WAL entries replayed:[/bold] {result.get('wal_entries', 0)}")
    console.print(f"[bold]Final status:[/bold] {result['status']}")


async def _resume_lite_run(run_id: str) -> dict[str, Any] | None:
    """Replay WAL entries and re-enter the executor for pending repos."""
    from regulatory_agent_kit.database.lite import (
        LiteAuditRepository,
        LitePipelineRunRepository,
        LiteRepositoryProgressRepository,
    )
    from regulatory_agent_kit.observability.wal import WriteAheadLog
    from regulatory_agent_kit.orchestration.lite import LiteModeExecutor

    run_data = await _get_lite_run(run_id)
    if run_data is None:
        return None

    if run_data.get("status", "") in TERMINAL_STATUSES:
        return {
            "error": f"Run is already in terminal state: {run_data['status']}",
            "status": run_data["status"],
        }

    # Replay WAL entries
    wal_path = Path.home() / ".rak" / f"wal-{run_id}.jsonl"
    wal = WriteAheadLog(wal_path)
    audit_repo = LiteAuditRepository(_LITE_DB_PATH)
    wal_count = await wal.replay(audit_repo)  # type: ignore[arg-type]

    # Get config from original run
    config_raw = run_data.get("config_snapshot", "{}")
    config = json.loads(config_raw) if isinstance(config_raw, str) else config_raw
    regulation_id = run_data.get("regulation_id", "")

    # Get repos that haven't completed
    progress_repo = LiteRepositoryProgressRepository(_LITE_DB_PATH)
    all_progress = await progress_repo.get_by_run(UUID(run_id))
    pending_urls = [
        p["repo_url"] for p in all_progress if p.get("status") not in TERMINAL_STATUSES
    ]

    if not pending_urls:
        # All repos already finished — mark run completed
        await LitePipelineRunRepository(_LITE_DB_PATH).update_status(
            UUID(run_id), "completed"
        )
        return {"wal_entries": wal_count, "status": "completed", "error": ""}

    # Re-run pending repos
    executor = LiteModeExecutor(db_path=_LITE_DB_PATH)
    result = await executor.run(
        regulation_id=regulation_id,
        repo_urls=pending_urls,
        plugin_data=config.get("plugin_data", {}),
        config=config,
    )

    return {"wal_entries": wal_count, "status": result.status, "error": ""}


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
    """Cancel a run by updating SQLite status and signalling Temporal if available."""
    from regulatory_agent_kit.database.lite import LitePipelineRunRepository

    run_info = await _get_lite_run(run_id)
    if run_info is None:
        return "not_found"

    if run_info.get("status", "") in TERMINAL_STATUSES:
        return "already_terminal"

    await LitePipelineRunRepository(_LITE_DB_PATH).update_status(UUID(run_id), "cancelled")

    # Try to cancel the Temporal workflow as well
    try:
        from temporalio.client import Client

        client = await Client.connect("localhost:7233")
        handle = client.get_workflow_handle(f"compliance-{run_id}")
        await handle.cancel()
        logger.info("Sent cancel signal to Temporal workflow %s", run_id)
    except Exception:
        logger.debug("Could not signal Temporal (Lite Mode or unavailable)")

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
# rak plugin publish
# ---------------------------------------------------------------------------


@plugin_app.command(name="publish")
def plugin_publish(
    path: Annotated[
        Path,
        typer.Argument(help="Path to the regulation plugin YAML file."),
    ],
    registry_url: Annotated[
        str,
        typer.Option(help="Registry API base URL."),
    ] = "http://localhost:8000",
    author: Annotated[
        str,
        typer.Option(help="Author name for the published plugin."),
    ] = "",
    tags: Annotated[
        str,
        typer.Option(help="Comma-separated tags."),
    ] = "",
) -> None:
    """Publish a regulation plugin to the remote registry."""
    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(code=1)

    loader = PluginLoader()
    try:
        plugin = loader.load(path)
    except (PluginLoadError, PluginValidationError) as exc:
        console.print(f"[red]Plugin validation failed: {exc}[/red]")
        raise typer.Exit(code=1) from None

    console.print(
        f"Publishing [cyan]{plugin.id}[/cyan] v{plugin.version} "
        f"({plugin.jurisdiction})..."
    )

    yaml_content = path.read_text(encoding="utf-8")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    _run_async(_publish_plugin(registry_url, yaml_content, author, tag_list))
    console.print(f"[green]Published {plugin.id} v{plugin.version}.[/green]")


async def _publish_plugin(
    registry_url: str,
    yaml_content: str,
    author: str,
    tags: list[str],
) -> None:
    """POST a plugin to the registry API."""
    import httpx

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{registry_url}/plugins",
            json={
                "yaml_content": yaml_content,
                "author": author,
                "tags": tags,
            },
        )
        if response.status_code not in (200, 201):
            console.print(f"[red]Registry error: {response.text}[/red]")
            raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# rak plugin install
# ---------------------------------------------------------------------------


@plugin_app.command(name="install")
def plugin_install(
    plugin_id: Annotated[
        str,
        typer.Argument(help="Plugin ID to install from the registry."),
    ],
    registry_url: Annotated[
        str,
        typer.Option(help="Registry API base URL."),
    ] = "http://localhost:8000",
    output_dir: Annotated[
        str,
        typer.Option(help="Directory to save the plugin."),
    ] = "regulations",
) -> None:
    """Download and install a regulation plugin from the remote registry."""
    console.print(f"Fetching [cyan]{plugin_id}[/cyan] from registry...")
    _run_async(_install_plugin(plugin_id, registry_url, output_dir))


async def _install_plugin(
    plugin_id: str,
    registry_url: str,
    output_dir: str,
) -> None:
    """Download a plugin's YAML from the registry and save it locally."""
    import httpx
    from ruamel.yaml import YAML

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{registry_url}/plugins/{plugin_id}/download")
        if response.status_code == 404:
            console.print(f"[red]Plugin '{plugin_id}' not found in registry.[/red]")
            raise typer.Exit(code=1)
        response.raise_for_status()
        payload = response.json()

    version = payload["version"]
    yaml_content = payload["yaml_content"]

    out_path = Path(output_dir) / plugin_id
    out_path.mkdir(parents=True, exist_ok=True)
    yaml_path = out_path / f"{plugin_id}.yaml"
    meta_path = out_path / "registry-metadata.json"

    yaml_writer = YAML()
    yaml_writer.default_flow_style = False
    with yaml_path.open("w", encoding="utf-8") as fh:
        yaml_writer.dump(yaml_content, fh)

    meta_path.write_text(
        json.dumps(
            {
                "plugin_id": plugin_id,
                "version": version,
                "yaml_hash": payload.get("yaml_hash", ""),
                "source": registry_url,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    console.print(
        f"[green]Installed {plugin_id} v{version} → {yaml_path}[/green]"
    )


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
    """Delete expired file analysis cache entries from PostgreSQL or SQLite."""
    # Try PostgreSQL first
    try:
        from regulatory_agent_kit.database.pool import get_pool

        pool = get_pool()
        from regulatory_agent_kit.database.repositories.file_analysis_cache import (
            FileAnalysisCacheRepository,
        )

        async with pool.connection() as conn:
            repo = FileAnalysisCacheRepository(conn)
            return await repo.delete_expired()
    except RuntimeError:
        pass

    # Fall back to Lite Mode SQLite
    if _LITE_DB_PATH.exists():
        from regulatory_agent_kit.database.lite import LiteFileAnalysisCacheRepository

        lite_repo = LiteFileAnalysisCacheRepository(_LITE_DB_PATH)
        return await lite_repo.delete_expired()

    return None


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
    """Create monthly range partitions for rak.audit_entries.

    Thin CLI wrapper delegating to :class:`PartitionManager`. Returns
    ``None`` when no PostgreSQL pool is available (e.g., Lite Mode).
    """
    try:
        from regulatory_agent_kit.database.pool import get_pool

        pool = get_pool()
    except RuntimeError:
        return None

    from regulatory_agent_kit.database.partition_manager import PartitionManager

    # The CLI argument is the number of months to create, including the
    # current one, while ``PartitionManager.months_ahead`` counts months
    # *in addition to* the current one.
    manager = PartitionManager(months_ahead=max(months - 1, 0))
    return await manager.ensure_future_partitions(pool)


# ---------------------------------------------------------------------------
# rak ci analyze
# ---------------------------------------------------------------------------


@ci_app.command(name="analyze")
def ci_analyze(
    repo_path: Annotated[
        str,
        typer.Option(help="Repository root directory to analyze."),
    ] = ".",
    output: Annotated[
        str | None,
        typer.Option(help="Path to write JSON report."),
    ] = None,
    format_type: Annotated[
        str,
        typer.Option("--format", help="Output format: json, markdown."),
    ] = "json",
) -> None:
    """Analyze CI/CD pipeline configurations for compliance gaps."""
    from regulatory_agent_kit.ci.pipeline_analyzer import (
        analyze_pipelines,
        format_pipeline_analysis_as_markdown,
    )

    root = Path(repo_path)
    if not root.is_dir():
        console.print(f"[red]Directory not found: {root}[/red]")
        raise typer.Exit(code=1)

    result = analyze_pipelines(root)

    if result.pipelines_analyzed == 0:
        console.print("[yellow]No CI/CD pipeline configs found.[/yellow]")
        raise typer.Exit(code=0)

    if output:
        out_path = Path(output)
        out_path.write_text(
            json.dumps(result.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        console.print(f"[green]Report written to {out_path}[/green]")

    if format_type == "markdown":
        console.print(format_pipeline_analysis_as_markdown(result))
    else:
        table = Table(title="CI/CD Pipeline Analysis")
        table.add_column("Check", style="cyan")
        table.add_column("Severity", style="white")
        table.add_column("Status", style="green")
        table.add_column("Detail")

        for finding in result.findings:
            status = "[green]PASS[/green]" if finding.passed else "[red]FAIL[/red]"
            table.add_row(
                finding.check_id,
                finding.severity.upper(),
                status,
                finding.detail or finding.description,
            )

        console.print(table)
        console.print(
            f"\n[bold]Pipelines: {result.pipelines_analyzed}[/bold] | "
            f"Checks: {result.checks_passed}/{result.checks_run} passed"
        )

    if result.checks_failed > 0:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
