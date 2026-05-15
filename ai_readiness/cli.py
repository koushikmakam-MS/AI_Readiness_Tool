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


def _run_personas_into_report(
    *,
    report,
    repo_path: Path,
    persona_ids: Optional[str],
    max_cost_usd: Optional[float],
    max_embed: Optional[int],
    concurrency: int,
    chat_model: Optional[str],
    embedding_model: Optional[str],
    verbose: bool,
) -> None:
    """Run the persona suite against ``repo_path`` and attach the result to ``report``."""
    import logging

    from ai_readiness.core.config import get_llm_config, load_config
    from ai_readiness.llm.client import LLMClient
    from ai_readiness.personas import load_persona_registry
    from ai_readiness.personas.cache import PersonaCache
    from ai_readiness.personas.persistence import persist_run
    from ai_readiness.personas.runner import PersonaRunner, RunOptions

    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    default_personas_yaml = (
        Path(__file__).parent.parent / "config" / "personas.yaml"
    )
    personas_cfg_path = (
        default_personas_yaml if default_personas_yaml.exists() else None
    )

    base_config = load_config(None)
    llm_config = get_llm_config(base_config)
    if chat_model:
        llm_config["model"] = chat_model
        llm_config["azure_deployment"] = chat_model
    if embedding_model:
        llm_config["embedding_model"] = embedding_model
        llm_config["azure_embedding_deployment"] = embedding_model

    client = LLMClient(llm_config)
    registry = load_persona_registry(personas_cfg_path)
    cache = PersonaCache(repo_path, enabled=True)
    runner = PersonaRunner(registry=registry, client=client, cache=cache)

    options = RunOptions(
        persona_ids=(
            [p.strip() for p in persona_ids.split(",") if p.strip()]
            if persona_ids
            else None
        ),
        max_embed=max_embed,
        max_cost_usd=max_cost_usd,
        concurrency=concurrency,
    )

    persona_report = None
    try:
        persona_report = runner.run(repo_path, options)
    finally:
        if persona_report is not None:
            persist_run(persona_report, cache)
        cache.close()

    if persona_report is not None:
        report.personas_report = persona_report


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
        help="Output format: terminal, json, markdown, pdf",
    ),
    output_path: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write the report to (required for --format pdf).",
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
    with_personas: bool = typer.Option(
        False,
        "--with-personas",
        help="Also run the persona-based doc readiness suite and embed the results in the report.",
    ),
    persona_ids: Optional[str] = typer.Option(
        None,
        "--personas",
        help="(With --with-personas) Comma-separated persona ids to run (default: all enabled).",
    ),
    personas_max_cost_usd: Optional[float] = typer.Option(
        None,
        "--personas-max-cost-usd",
        help="(With --with-personas) Hard abort once persona spend exceeds this.",
    ),
    personas_max_embed: Optional[int] = typer.Option(
        None,
        "--personas-max-embed",
        help="(With --with-personas) Cap chunks embedded for persona scoring.",
    ),
    personas_concurrency: int = typer.Option(
        5,
        "--personas-concurrency",
        help="(With --with-personas) Parallel LLM calls for persona scoring.",
    ),
    chat_model: Optional[str] = typer.Option(
        None,
        "--chat-model",
        help="(With --with-personas) Override chat model / Azure deployment.",
    ),
    embedding_model: Optional[str] = typer.Option(
        None,
        "--embedding-model",
        help="(With --with-personas) Override embedding model / Azure deployment.",
    ),
    show_cost: bool = typer.Option(
        False,
        "--show-cost",
        help="Include cost information (USD) in the report output.",
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

            if with_personas:
                _run_personas_into_report(
                    report=report,
                    repo_path=repo_path,
                    persona_ids=persona_ids,
                    max_cost_usd=personas_max_cost_usd,
                    max_embed=personas_max_embed,
                    concurrency=personas_concurrency,
                    chat_model=chat_model,
                    embedding_model=embedding_model,
                    verbose=verbose,
                )

            output = format_report(
                report,
                format=output_format,
                verbose=verbose,
                output_path=output_path,
                show_cost=show_cost,
            )
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


@app.command(name="personas")
def personas(
    target: str = typer.Argument(
        ".",
        help="Local path or Git URL of the repo to evaluate (read-only).",
    ),
    clone_dir: Optional[str] = typer.Option(
        None, "--clone-dir", "-d", help="Where to clone remote repos."
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--personas-config",
        help="Path to personas.yaml override (defaults to config/personas.yaml).",
    ),
    persona_ids: Optional[str] = typer.Option(
        None,
        "--personas",
        "-p",
        help="Comma-separated persona ids to run (default: all enabled).",
    ),
    output_format: str = typer.Option(
        "terminal", "--format", "-f", help="terminal | json | markdown"
    ),
    top_k: Optional[int] = typer.Option(
        None, "--top-k", help="Number of top-relevance docs each persona scores."
    ),
    max_docs: Optional[int] = typer.Option(
        None, "--max-docs", help="Hard cap on docs scored per persona."
    ),
    max_embed: Optional[int] = typer.Option(
        None,
        "--max-embed",
        help="Cap total chunks to embed (helpful when Azure quota is tight). "
        "Top-level docs are kept first.",
    ),
    sample: Optional[int] = typer.Option(
        None, "--sample", help="Random sample N docs from the persona's shortlist."
    ),
    max_cost_usd: Optional[float] = typer.Option(
        None, "--max-cost-usd", help="Hard abort once estimated spend exceeds this."
    ),
    concurrency: int = typer.Option(
        5, "--concurrency", help="Parallel LLM calls per persona."
    ),
    no_simulated_task: bool = typer.Option(
        False, "--no-simulated-task", help="Skip the per-persona simulated task."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print cost estimate without calling the LLM."
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Disable embedding/score cache for this run."
    ),
    clear_cache: bool = typer.Option(
        False, "--clear-cache", help="Wipe the cache for this repo before running."
    ),
    cache_dir: Optional[Path] = typer.Option(
        None, "--cache-dir", help="Override cache root (default ~/.ai-readiness/cache)."
    ),
    cache_key: Optional[str] = typer.Option(
        None, "--cache-key", help="Override cache key for this repo."
    ),
    chat_model: Optional[str] = typer.Option(
        None, "--chat-model", help="Override chat model / Azure deployment name."
    ),
    embedding_model: Optional[str] = typer.Option(
        None,
        "--embedding-model",
        help="Override embedding model / Azure deployment name.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    github_token: Optional[str] = typer.Option(
        None, "--github-token", envvar="GITHUB_TOKEN"
    ),
    show_cost: bool = typer.Option(
        False,
        "--show-cost",
        help="Include cost information (USD) in the report output.",
    ),
) -> None:
    """Score docs through multiple AI-agent personas (Dora, Sherlock, etc.)."""
    import logging

    from ai_readiness.core.config import get_llm_config, load_config
    from ai_readiness.llm.client import LLMClient
    from ai_readiness.personas import load_persona_registry
    from ai_readiness.personas.cache import PersonaCache
    from ai_readiness.personas.persistence import persist_run
    from ai_readiness.personas.reporter import (
        render_terminal,
        to_json,
        to_markdown,
    )
    from ai_readiness.personas.runner import PersonaRunner, RunOptions

    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    default_personas_yaml = Path(__file__).parent.parent / "config" / "personas.yaml"
    personas_cfg_path = config_file or (
        default_personas_yaml if default_personas_yaml.exists() else None
    )

    try:
        with RepoResolver(target, clone_dir, github_token=github_token) as resolver:
            repo_path = resolver.resolve()

            base_config = load_config(None)
            llm_config = get_llm_config(base_config)
            if chat_model:
                llm_config["model"] = chat_model
                llm_config["azure_deployment"] = chat_model
            if embedding_model:
                llm_config["embedding_model"] = embedding_model
                llm_config["azure_embedding_deployment"] = embedding_model
            client = LLMClient(llm_config)

            registry = load_persona_registry(personas_cfg_path)

            cache = PersonaCache(
                repo_path,
                cache_root=cache_dir,
                cache_key_override=cache_key,
                enabled=not no_cache,
            )
            if clear_cache:
                cache.clear()

            runner = PersonaRunner(registry=registry, client=client, cache=cache)

            options = RunOptions(
                persona_ids=(
                    [p.strip() for p in persona_ids.split(",") if p.strip()]
                    if persona_ids
                    else None
                ),
                top_k=top_k,
                max_docs_per_persona=max_docs,
                max_embed=max_embed,
                sample=sample,
                max_cost_usd=max_cost_usd,
                concurrency=concurrency,
                dry_run=dry_run,
                simulated_tasks=False if no_simulated_task else None,
            )

            report = None
            try:
                report = runner.run(repo_path, options)
            finally:
                run_dir = None
                if report is not None and not dry_run:
                    run_dir = persist_run(report, cache)
                cache.close()

            if report is None:
                return

            fmt = output_format.lower()
            if fmt == "json":
                console.print(to_json(report))
            elif fmt in ("md", "markdown"):
                console.print(to_markdown(report, show_cost=show_cost))
            else:
                render_terminal(report, console, verbose=verbose, show_cost=show_cost)
            if run_dir is not None:
                console.print(f"[dim]Run saved to {run_dir}[/dim]")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(code=130)


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


@app.command()
def adoption(
    action: str = typer.Argument(
        "show",
        help="Action: 'fetch' to pull latest stats, 'show' to display dashboard, 'report' to generate HTML email.",
    ),
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        "-r",
        help="GitHub owner/repo slug (e.g. koushikmakam-MS/AI_Readiness_Tool). "
        "Auto-detected from git remote if omitted.",
    ),
    output_format: str = typer.Option(
        "terminal",
        "--format",
        "-f",
        help="Output format: terminal, json",
    ),
    output_path: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="(report only) Path to write the HTML report file.",
    ),
    data_dir: Optional[Path] = typer.Option(
        None,
        "--data-dir",
        help="Override the repo root used for storing adoption data "
        "(default: git repo root).",
    ),
) -> None:
    """Track adoption metrics (GitHub clones, views, forks, stars)."""
    import re
    import subprocess

    from ai_readiness.adoption.dashboard import render_dashboard
    from ai_readiness.adoption.github_tracker import fetch_github_stats
    from ai_readiness.adoption.store import append_snapshot

    # Resolve repo root for data storage
    repo_root = data_dir
    if repo_root is None:
        try:
            root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            repo_root = Path(root.stdout.strip()) if root.returncode == 0 else Path(".")
        except FileNotFoundError:
            repo_root = Path(".")

    act = action.lower().strip()

    if act == "show":
        render_dashboard(repo_root, console, output_format=output_format)
        return

    if act == "report":
        from ai_readiness.adoption.email_report import generate_adoption_email

        html = generate_adoption_email(repo_root)
        out = output_path or (repo_root / "adoption_data" / "adoption_report.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        console.print(f"[green]✓[/green] Report saved to [bold]{out}[/bold]")
        console.print("[dim]Open the file in a browser, then copy/paste into an email.[/dim]")
        return

    # Resolve owner/repo slug (only needed for fetch)
    owner_repo = repo
    if not owner_repo:
        owner_repo = _detect_github_slug()
    if not owner_repo:
        console.print(
            "[red]Error:[/red] Could not detect GitHub repo. "
            "Pass [bold]--repo owner/repo[/bold] explicitly."
        )
        raise typer.Exit(code=1)

    if act == "fetch":
        console.print(f"[cyan]Fetching adoption data for [bold]{owner_repo}[/bold]…[/cyan]")
        try:
            snapshot = fetch_github_stats(owner_repo)
        except RuntimeError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)

        path = append_snapshot(repo_root, snapshot)
        console.print(f"[green]✓[/green] Snapshot saved to [bold]{path}[/bold]")
        console.print()
        render_dashboard(repo_root, console, output_format=output_format)

    else:
        console.print(f"[red]Unknown action:[/red] {action}. Use 'fetch', 'show', or 'report'.")
        raise typer.Exit(code=1)


def _detect_github_slug() -> Optional[str]:
    """Try to extract ``owner/repo`` from the git remotes."""
    import re
    import subprocess

    try:
        result = subprocess.run(
            ["git", "remote", "-v"], capture_output=True, text=True
        )
    except FileNotFoundError:
        return None

    for line in result.stdout.splitlines():
        m = re.search(r"github\.com[:/]([^/]+/[^/\s]+?)(?:\.git)?(?:\s|$)", line)
        if m:
            return m.group(1)
    return None


def main() -> None:
    app()


if __name__ == "__main__":
    main()
