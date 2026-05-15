"""Rich terminal dashboard for adoption metrics."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ai_readiness.adoption.store import load_history


# ── Sparkline helper ─────────────────────────────────────────────────────────

_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[int | float]) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo if hi != lo else 1
    return "".join(_SPARK_CHARS[min(int((v - lo) / span * 7), 7)] for v in values)


# ── Public API ────────────────────────────────────────────────────────────────


def render_dashboard(
    repo_root: Path,
    console: Console,
    *,
    output_format: str = "terminal",
) -> None:
    """Render the adoption dashboard from stored history."""
    history = load_history(repo_root)

    if not history.get("snapshots"):
        console.print(
            "[yellow]No adoption data yet.[/yellow]  Run "
            "[bold]ai-readiness adoption fetch <owner/repo>[/bold] first."
        )
        return

    if output_format == "json":
        console.print(json.dumps(history, indent=2, default=str))
        return

    latest = history["snapshots"][-1]
    repo_name = history.get("repo", "unknown")

    # ── Header ──
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{repo_name}[/bold cyan]  ·  "
            f"Last fetched: [dim]{_fmt_ts(latest.get('timestamp', ''))}[/dim]",
            title="📊 Adoption Dashboard",
            border_style="bright_blue",
        )
    )

    # ── Summary cards ──
    summary = Table.grid(padding=(0, 3))
    summary.add_row(
        _metric_card("⭐ Stars", latest.get("stars", 0)),
        _metric_card("🍴 Forks", latest.get("forks_count", 0)),
        _metric_card("👀 Watchers", latest.get("watchers", 0)),
        _metric_card("🐛 Issues", latest.get("open_issues", 0)),
    )
    console.print(summary)
    console.print()

    # ── Clone & View traffic ──
    traffic_table = Table(
        title="Traffic (rolling 14-day window)",
        show_header=True,
        header_style="bold magenta",
    )
    traffic_table.add_column("Metric", style="cyan")
    traffic_table.add_column("Total", justify="right")
    traffic_table.add_column("Unique", justify="right")
    traffic_table.add_column("Trend (daily)", min_width=20)

    clones = latest.get("clones", {})
    views = latest.get("views", {})

    daily_clones = history.get("daily_clones", [])
    daily_views = history.get("daily_views", [])

    traffic_table.add_row(
        "Clones",
        str(clones.get("total", 0)),
        str(clones.get("unique", 0)),
        _sparkline([d.get("count", 0) for d in daily_clones[-30:]]),
    )
    traffic_table.add_row(
        "Views",
        str(views.get("total", 0)),
        str(views.get("unique", 0)),
        _sparkline([d.get("count", 0) for d in daily_views[-30:]]),
    )
    console.print(traffic_table)
    console.print()

    # ── Daily breakdown ──
    if daily_clones or daily_views:
        daily_table = Table(
            title="Daily Breakdown (last 14 days)",
            show_header=True,
            header_style="bold green",
        )
        daily_table.add_column("Date", style="dim")
        daily_table.add_column("Clones", justify="right")
        daily_table.add_column("Unique Clones", justify="right")
        daily_table.add_column("Views", justify="right")
        daily_table.add_column("Unique Views", justify="right")

        # Build a merged date map
        dates: dict[str, dict] = {}
        for d in daily_clones:
            dt = d["timestamp"][:10]
            dates.setdefault(dt, {})["clones"] = d.get("count", 0)
            dates[dt]["u_clones"] = d.get("uniques", 0)
        for d in daily_views:
            dt = d["timestamp"][:10]
            dates.setdefault(dt, {})["views"] = d.get("count", 0)
            dates[dt]["u_views"] = d.get("uniques", 0)

        for dt in sorted(dates)[-14:]:
            row = dates[dt]
            daily_table.add_row(
                dt,
                str(row.get("clones", 0)),
                str(row.get("u_clones", 0)),
                str(row.get("views", 0)),
                str(row.get("u_views", 0)),
            )
        console.print(daily_table)
        console.print()

    # ── Top referrers ──
    referrers = latest.get("top_referrers", [])
    if referrers:
        ref_table = Table(
            title="Top Referrers",
            show_header=True,
            header_style="bold yellow",
        )
        ref_table.add_column("Source", style="cyan")
        ref_table.add_column("Views", justify="right")
        ref_table.add_column("Unique", justify="right")
        for r in referrers:
            ref_table.add_row(r["name"], str(r["views"]), str(r["unique"]))
        console.print(ref_table)
        console.print()

    # ── Fork owners ──
    all_forks = history.get("all_fork_owners", [])
    if all_forks:
        console.print(
            Panel(
                ", ".join(f"[cyan]{f}[/cyan]" for f in all_forks),
                title="🍴 Fork Owners",
                border_style="green",
            )
        )
        console.print()

    # ── Snapshot history ──
    snapshots = history.get("snapshots", [])
    if len(snapshots) > 1:
        hist_table = Table(
            title=f"Fetch History ({len(snapshots)} snapshots)",
            show_header=True,
            header_style="bold",
        )
        hist_table.add_column("Date", style="dim")
        hist_table.add_column("Stars", justify="right")
        hist_table.add_column("Forks", justify="right")
        hist_table.add_column("Clones (unique)", justify="right")
        hist_table.add_column("Views (unique)", justify="right")

        for snap in snapshots[-10:]:
            c = snap.get("clones", {})
            v = snap.get("views", {})
            hist_table.add_row(
                _fmt_ts(snap.get("timestamp", "")),
                str(snap.get("stars", 0)),
                str(snap.get("forks_count", 0)),
                f"{c.get('total', 0)} ({c.get('unique', 0)})",
                f"{v.get('total', 0)} ({v.get('unique', 0)})",
            )
        console.print(hist_table)
        console.print()

    # ── Tip ──
    console.print(
        "[dim]💡 Run [bold]ai-readiness adoption fetch[/bold] periodically "
        "(or via CI) to build trend data. GitHub traffic API retains only 14 days.[/dim]"
    )
    console.print()


def _metric_card(label: str, value: int | str) -> Panel:
    return Panel(
        f"[bold white]{value}[/bold white]",
        title=label,
        border_style="bright_blue",
        width=18,
    )


def _fmt_ts(ts: str) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts[:16]
