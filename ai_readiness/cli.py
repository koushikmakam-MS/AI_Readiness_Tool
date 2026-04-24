"""CLI entry point for AI Readiness Tool."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ai_readiness.core.config import init_user_config, load_config
from ai_readiness.core.engine import AssessmentEngine
from ai_readiness.core.repo_resolver import RepoResolver
from ai_readiness.core.reporter import format_report

app = typer.Typer(
    name="ai-readiness",
    help="Assess how AI coding agent friendly your repository is.",
    add_completion=False,
)
console = Console()


@app.command()
def check(
    target: str = typer.Argument(
        ".",
        help="Local path or Git URL (e.g., https://github.com/owner/repo or owner/repo)",
    ),
    clone_dir: Optional[str] = typer.Option(
        None,
        "--clone-dir",
        "-d",
        help="Directory to clone remote repos into (default: temp directory)",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to custom config YAML file",
    ),
    output_format: str = typer.Option(
        "terminal",
        "--format",
        "-f",
        help="Output format: terminal, json, markdown",
    ),
    no_llm: bool = typer.Option(
        False,
        "--no-llm",
        help="Disable LLM analysis (static checks only)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    github_token: Optional[str] = typer.Option(
        None,
        "--github-token",
        envvar="GITHUB_TOKEN",
        help="GitHub token for cloning private repos (or set GITHUB_TOKEN env var)",
    ),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        "-a",
        help="Comma-separated list of target AI agents (e.g., copilot,cursor,claude,aider). Only these are scored.",
    ),
) -> None:
    """Assess a repository's AI coding agent readiness."""
    try:
        with RepoResolver(target, clone_dir, github_token=github_token) as resolver:
            repo_path = resolver.resolve()
            config = load_config(config_file)

            # Apply --agents override to config
            if agents:
                agent_list = [a.strip().lower() for a in agents.split(",") if a.strip()]
                if "assessment" not in config or config["assessment"] is None:
                    config["assessment"] = {}
                config["assessment"]["target_agents"] = agent_list

            engine = AssessmentEngine(config=config, repo_path=repo_path, no_llm=no_llm)
            report = engine.run()

            output = format_report(report, format=output_format, verbose=verbose)
            if output:
                console.print(output)

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(code=130)


@app.command(name="init-config")
def init_config(
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="OpenAI API key to store in config",
    ),
) -> None:
    """Initialize user configuration at ~/.ai-readiness/config.yaml."""
    path = init_user_config(api_key=api_key)
    console.print(f"[green]✓[/green] Config created at {path}")
    if not api_key:
        console.print("[dim]Edit the file to add your OpenAI API key for LLM analysis.[/dim]")


@app.command(name="list-checkers")
def list_checkers(
    config_file: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """List all configured assessment dimensions/checkers."""
    from rich.table import Table

    config = load_config(config_file)
    dims = config.get("dimensions", {})

    table = Table(title="Configured Dimensions")
    table.add_column("ID", style="cyan")
    table.add_column("Checker Class", style="dim")
    table.add_column("Weight", justify="right")
    table.add_column("Enabled", justify="center")

    for dim_id, dim_cfg in dims.items():
        table.add_row(
            dim_id,
            dim_cfg.get("checker", "N/A"),
            str(dim_cfg.get("weight", "?")),
            "✓" if dim_cfg.get("enabled", True) else "✗",
        )

    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
