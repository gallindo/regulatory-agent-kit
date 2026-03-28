"""CLI entry point for regulatory-agent-kit.

Provides the ``rak`` command with subcommands for running compliance pipelines,
managing pipeline state, validating regulation plugins, and database maintenance.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from regulatory_agent_kit.config import load_settings
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
        uuid.UUID(value)
    except ValueError:
        msg = f"Invalid UUID: {value}"
        raise typer.BadParameter(msg) from None
    return value


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
    # Load settings with optional YAML overlay
    overrides: dict[str, object] = {}
    if lite:
        overrides["lite_mode"] = True
    if checkpoint_mode != "terminal":
        overrides["checkpoint_mode"] = checkpoint_mode

    settings = load_settings(
        yaml_path=config,
        overrides=overrides,
    )

    # Validate the regulation plugin
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
        typer.echo("Lite Mode pipeline execution is not yet implemented.")
    else:
        typer.echo("Temporal pipeline execution is not yet implemented.")


# ---------------------------------------------------------------------------
# rak status
# ---------------------------------------------------------------------------


@app.command()
def status(
    run_id: Annotated[
        str,
        typer.Option(help="Pipeline run ID (UUID)."),
    ],
) -> None:
    """Query and display pipeline run status."""
    run_id = _validate_uuid(run_id)

    table = Table(title=f"Pipeline Status: {run_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Run ID", run_id)
    table.add_row("Status", "unknown (not yet connected to backend)")
    table.add_row("Repos", "—")
    table.add_row("Progress", "—")
    console.print(table)


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
    typer.echo(f"Retrying failures for run: {run_id}")
    typer.echo("Not yet implemented — would query failed repos and re-dispatch.")


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
    if dry_run:
        typer.echo(f"[DRY RUN] Would rollback run: {run_id}")
        typer.echo("Not yet implemented — would read rollback manifest and preview.")
    else:
        typer.echo(f"Rolling back run: {run_id}")
        typer.echo("Not yet implemented — would read rollback manifest and execute.")


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
    typer.echo(f"Resuming run: {run_id}")
    typer.echo("Not yet implemented — would reload WAL and resume from last checkpoint.")


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
    typer.echo(f"Cancelling run: {run_id}")
    typer.echo("Not yet implemented — would signal pipeline cancellation.")


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
# rak db clean-cache
# ---------------------------------------------------------------------------


@db_app.command(name="clean-cache")
def db_clean_cache() -> None:
    """Invoke cache cleanup on the file analysis cache."""
    typer.echo("Cleaning analysis cache...")
    typer.echo("Not yet implemented — would delete expired cache entries.")


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
    typer.echo(f"Creating {months} month(s) of audit partitions...")
    typer.echo("Not yet implemented — would create PostgreSQL range partitions.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
