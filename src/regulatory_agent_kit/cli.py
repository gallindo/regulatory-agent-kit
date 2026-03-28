"""CLI entry point for regulatory-agent-kit."""

import typer

app = typer.Typer(
    name="rak",
    help="regulatory-agent-kit — AI-powered regulatory compliance automation",
    no_args_is_help=True,
)


@app.command()
def run(
    regulation: str = typer.Option(..., help="Path to regulation plugin YAML"),
    repos: list[str] = typer.Option(..., help="Repository URLs or local paths to analyze"),
    checkpoint_mode: str = typer.Option("terminal", help="Approval mode: terminal|slack|email|webhook"),
    lite: bool = typer.Option(False, help="Run in Lite Mode (no external services)"),
) -> None:
    """Run the compliance pipeline against target repositories."""
    typer.echo(f"Running regulation: {regulation}")


@app.command()
def status(
    run_id: str = typer.Option(..., help="Pipeline run ID"),
) -> None:
    """Check pipeline run status."""
    typer.echo(f"Status for run: {run_id}")


if __name__ == "__main__":
    app()
