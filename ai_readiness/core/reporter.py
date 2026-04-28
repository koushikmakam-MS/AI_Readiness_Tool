"""Report formatters — terminal (rich), JSON, and Markdown output."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ai_readiness.core.models import CategoryScore, CheckStatus, DimensionScore, Rating, Report

# ── Colour / icon helpers ────────────────────────────────────────────

_STATUS_STYLE: dict[CheckStatus, str] = {
    CheckStatus.PASS: "green",
    CheckStatus.FAIL: "red",
    CheckStatus.WARN: "yellow",
    CheckStatus.SKIP: "dim",
}

_STATUS_ICON: dict[CheckStatus, str] = {
    CheckStatus.PASS: "✓",
    CheckStatus.FAIL: "✗",
    CheckStatus.WARN: "⚠",
    CheckStatus.SKIP: "○",
}

_RATING_STYLE: dict[Rating, str] = {
    Rating.POOR: "bold red",
    Rating.FAIR: "bold yellow",
    Rating.GOOD: "bold green",
    Rating.EXCELLENT: "bold magenta",
}

_CATEGORY_EMOJI = {
    "ai_onboarding": "🚀",
    "ai_coding": "🤖",
    "repo_health": "🏥",
}


def _score_bar(score: float, width: int = 10) -> str:
    """Render a bar of █ and ░ blocks for a 0-10 score."""
    filled = round(score)
    return "█" * filled + "░" * (width - filled)


def _score_color(score: float) -> str:
    return "green" if score >= 7 else "yellow" if score >= 4 else "red"


# ── Terminal (rich) reporter ─────────────────────────────────────────


class TerminalReporter:
    """Pretty-print a report to the terminal via rich."""

    def __init__(self, verbose: bool = False, show_cost: bool = False) -> None:
        self.verbose = verbose
        self.show_cost = show_cost
        self.console = Console()

    def print(self, report: Report) -> None:
        self.console.print()

        # Header
        self._print_header(report)

        if report.categories:
            self._print_category_summary(report)
            if self.verbose:
                for cat in report.categories:
                    self._print_category_detail(cat)
        else:
            # Fallback: legacy flat dimension view
            self._print_summary_table(report)
            if self.verbose:
                for dim in report.dimensions:
                    self._print_dimension_detail(dim)

        # Recommendations
        self._print_recommendations(report)

        # Personas (if attached via --with-personas)
        if report.personas_report is not None:
            self._print_personas(report.personas_report)

        # LLM summary
        if report.llm_summary:
            self.console.print(
                Panel(report.llm_summary, title="🤖 LLM Summary", border_style="cyan")
            )

        self.console.print()

    # ---- private helpers ----

    def _print_header(self, report: Report) -> None:
        rating = report.rating
        style = _RATING_STYLE[rating]
        langs = ", ".join(report.languages_detected) if report.languages_detected else "none detected"

        header = Text.assemble(
            ("AI Readiness Report\n", "bold underline"),
            ("Repo: ", "dim"),
            (report.repo_path, ""),
            ("\nLanguages: ", "dim"),
            (langs, ""),
        )
        self.console.print(Panel(header, border_style="blue"))

        score_text = Text.assemble(
            (f"{rating.emoji} Overall Score: ", "bold"),
            (f"{report.overall_score:.1f}/100", style),
            (f"  ({rating.value})", style),
        )
        self.console.print(score_text)
        self.console.print()

    def _print_category_summary(self, report: Report) -> None:
        """Print 3-category summary table."""
        table = Table(title="Category Scores", show_lines=True, expand=False)
        table.add_column("Category", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Bar")
        table.add_column("Checks", justify="center")
        table.add_column("Weight", justify="right", style="dim")

        for cat in report.categories:
            color = _score_color(cat.score)
            emoji = _CATEGORY_EMOJI.get(cat.category_id, "📊")
            table.add_row(
                f"{emoji} {cat.category_name}",
                f"[{color}]{cat.score:.1f}/10[/{color}]",
                f"[{color}]{_score_bar(cat.score)}[/{color}]",
                f"{cat.passed_checks}/{cat.total_checks}",
                f"{cat.weight:.0f}%",
            )

        self.console.print(table)
        self.console.print()

    def _print_category_detail(self, cat: CategoryScore) -> None:
        """Print detailed checks for a category."""
        emoji = _CATEGORY_EMOJI.get(cat.category_id, "📊")
        color = _score_color(cat.score)
        self.console.print(
            f"[bold]{emoji} {cat.category_name}[/bold]"
            f"  [{color}]{cat.score:.1f}/10[/{color}]"
            f"  [dim]— {cat.description}[/dim]"
        )

        for check in cat.checks:
            icon = _STATUS_ICON[check.status]
            style = _STATUS_STYLE[check.status]
            scorable_tag = "" if check.scorable else " [dim](info)[/dim]"
            score_tag = f" [{style}]({check.raw_score:.0f}/10)[/{style}]" if check.raw_score is not None else ""
            self.console.print(
                f"  [{style}]{icon}[/{style}] {check.name}{score_tag}: {check.message}{scorable_tag}"
            )
            if check.details:
                self.console.print(f"    [dim]{check.details}[/dim]")

        if cat.llm_insights:
            self.console.print(
                Panel(cat.llm_insights, title="LLM Insights", border_style="cyan", padding=(0, 1))
            )
        self.console.print()

    def _print_summary_table(self, report: Report) -> None:
        table = Table(title="Dimension Scores", show_lines=False, expand=False)
        table.add_column("Dimension", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Bar")
        table.add_column("Checks", justify="center")
        table.add_column("Weight", justify="right", style="dim")

        for dim in report.dimensions:
            color = _score_color(dim.score)
            table.add_row(
                dim.dimension_name,
                f"[{color}]{dim.score:.1f}/10[/{color}]",
                f"[{color}]{_score_bar(dim.score)}[/{color}]",
                f"{dim.passed_checks}/{dim.total_checks}",
                f"{dim.weight:.0f}%",
            )

        self.console.print(table)
        self.console.print()

    def _print_dimension_detail(self, dim: DimensionScore) -> None:
        self.console.print(f"[bold]── {dim.dimension_name} ──[/bold]")
        for check in dim.checks:
            icon = _STATUS_ICON[check.status]
            style = _STATUS_STYLE[check.status]
            self.console.print(f"  [{style}]{icon}[/{style}] {check.name}: {check.message}")
            if check.details:
                self.console.print(f"    [dim]{check.details}[/dim]")
        if dim.llm_insights:
            self.console.print(
                Panel(dim.llm_insights, title="LLM Insights", border_style="cyan", padding=(0, 1))
            )
        self.console.print()

    def _print_recommendations(self, report: Report) -> None:
        recs = report.recommendations
        if not recs:
            return
        self.console.print("[bold]📋 Top Recommendations[/bold]")
        for i, rec in enumerate(recs[:10], 1):
            self.console.print(f"  {i}. {rec}")
        self.console.print()

    def _print_personas(self, persona_report: Any) -> None:
        """Render the persona suite block on the terminal."""
        overall = persona_report.overall
        color = _score_color(overall.overall_score / 10.0)
        cost_part = f", cost ${overall.total_cost_usd:.4f}" if self.show_cost else ""
        self.console.print(
            f"[bold]🎭 Persona Doc Readiness[/bold]  "
            f"[{color}]{overall.overall_score:.1f}/100[/{color}]  "
            f"[dim](docs analysed: {persona_report.docs_total}, "
            f"chunks scored: {persona_report.chunks_total}"
            f"{cost_part})[/dim]"
        )

        table = Table(show_header=True, header_style="bold")
        table.add_column("Persona", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Docs", justify="right")
        if self.show_cost:
            table.add_column("Cost", justify="right", style="dim")
        for r in persona_report.persona_results:
            score_color = _score_color(r.overall_score / 10.0)
            row = [
                f"{r.display_name}",
                f"[{score_color}]{r.overall_score:.1f}[/{score_color}]",
                str(len(r.rubric_scores)),
            ]
            if self.show_cost:
                row.append(f"${r.estimated_cost_usd:.4f}")
            table.add_row(*row)
        self.console.print(table)
        self.console.print()


# ── JSON reporter ────────────────────────────────────────────────────


class JSONReporter:
    """Serialize a report to a JSON string."""

    @staticmethod
    def render(report: Report) -> str:
        def _check(c: Any) -> dict[str, Any]:
            return {
                "name": c.name,
                "status": c.status.value,
                "message": c.message,
                "recommendation": c.recommendation,
                "raw_score": c.raw_score,
                "scorable": c.scorable,
            }

        def _cat(c: CategoryScore) -> dict[str, Any]:
            return {
                "id": c.category_id,
                "name": c.category_name,
                "description": c.description,
                "score": round(c.score, 2),
                "weight": c.weight,
                "passed_checks": c.passed_checks,
                "total_checks": c.total_checks,
                "checks": [_check(ch) for ch in c.checks],
                "llm_insights": c.llm_insights,
            }

        def _dim(d: DimensionScore) -> dict[str, Any]:
            return {
                "id": d.dimension_id,
                "name": d.dimension_name,
                "score": round(d.score, 2),
                "weight": d.weight,
                "checks": [_check(ch) for ch in d.checks],
                "llm_insights": d.llm_insights,
            }

        payload: dict[str, Any] = {
            "repo_path": report.repo_path,
            "overall_score": round(report.overall_score, 2),
            "rating": report.rating.value,
            "languages": report.languages_detected,
            "categories": [_cat(c) for c in report.categories] if report.categories else None,
            "dimensions": [_dim(d) for d in report.dimensions],
            "recommendations": report.recommendations,
            "llm_summary": report.llm_summary,
        }
        if report.personas_report is not None:
            pr = report.personas_report
            payload["personas"] = {
                "overall_score": round(pr.overall.overall_score, 2),
                "docs_total": pr.docs_total,
                "chunks_total": pr.chunks_total,
                "total_cost_usd": round(pr.overall.total_cost_usd, 4),
                "per_persona": [
                    {
                        "persona_id": r.persona_id,
                        "display_name": r.display_name,
                        "score": round(r.overall_score, 2),
                        "docs_scored": len(r.rubric_scores),
                        "estimated_cost_usd": round(r.estimated_cost_usd, 4),
                    }
                    for r in pr.persona_results
                ],
            }
        return json.dumps(payload, indent=2, ensure_ascii=False)


# ── Markdown reporter ────────────────────────────────────────────────


class MarkdownReporter:
    """Render a report as a Markdown document."""

    @staticmethod
    def _render_personas(report: Report, show_cost: bool = False) -> list[str]:
        """Render the persona doc readiness section."""
        lines: list[str] = []
        if report.personas_report is None:
            return lines
        pr = report.personas_report
        lines.append("## 🎭 Persona Doc Readiness")
        lines.append("")
        lines.append(
            "Each persona represents a different AI agent role. They evaluate your "
            "documentation from their unique perspective — asking whether the docs "
            "give them enough context to do their job without hallucinating."
        )
        lines.append("")
        overall_line = (
            f"**Overall:** {pr.overall.overall_score:.1f} / 100  "
            f"· Docs analysed: {pr.docs_total}  "
            f"· Chunks scored: {pr.chunks_total}"
        )
        if show_cost:
            overall_line += f"  · Cost: ${pr.overall.total_cost_usd:.4f}"
        lines.append(overall_line)
        lines.append("")
        if show_cost:
            lines.append("| Persona | Role | Score (/100) | Docs scored | Cost (USD) |")
            lines.append("|---------|------|-------------:|------------:|-----------:|")
        else:
            lines.append("| Persona | Role | Score (/100) | Docs scored |")
            lines.append("|---------|------|-------------:|------------:|")
        for r in pr.persona_results:
            role = getattr(r, "role", "") or "—"
            row = (
                f"| {r.display_name} (`{r.persona_id}`) "
                f"| {role} "
                f"| {r.overall_score:.1f}/100 "
                f"| {len(r.rubric_scores)} "
            )
            if show_cost:
                row += f"| ${r.estimated_cost_usd:.4f} |"
            else:
                row += "|"
            lines.append(row)
        lines.append("")
        lines.append("### How Scores Work")
        lines.append("")
        lines.append("Every doc is scored on three dimensions (1–5 each):")
        lines.append("")
        lines.append("| Dimension | What It Measures |")
        lines.append("|-----------|-----------------|")
        lines.append(
            "| **Context Sufficiency** | Does the doc give the AI agent enough "
            "information to complete its task without guessing? |"
        )
        lines.append(
            "| **Ambiguity / Hallucination Risk** | Could vague or contradictory "
            "content cause the AI to produce incorrect code? |"
        )
        lines.append(
            "| **Token Efficiency** | Is the signal-to-noise ratio worth the "
            "context window space? |"
        )
        lines.append("")
        return lines

    @staticmethod
    def render(report: Report, show_cost: bool = False) -> str:
        lines: list[str] = []
        rating = report.rating

        lines.append(f"# {rating.emoji} AI Readiness Report")
        lines.append("")
        lines.append(f"**Repository:** `{report.repo_path}`  ")
        lines.append(f"**Overall Score:** {report.overall_score:.1f} / 100 ({rating.value})  ")
        if report.languages_detected:
            lines.append(f"**Languages:** {', '.join(report.languages_detected)}")
        lines.append("")

        if report.categories:
            # Category-based output
            lines.append("## Category Scores")
            lines.append("")
            lines.append("| Category | Score | Checks | Weight |")
            lines.append("|----------|------:|-------:|-------:|")
            for cat in report.categories:
                emoji = _CATEGORY_EMOJI.get(cat.category_id, "📊")
                lines.append(
                    f"| {emoji} {cat.category_name} | {cat.score:.1f}/10 "
                    f"| {cat.passed_checks}/{cat.total_checks} | {cat.weight:.0f}% |"
                )
            lines.append("")

            # Persona doc readiness right after category scores
            lines.extend(MarkdownReporter._render_personas(report, show_cost=show_cost))

            lines.append("## Detailed Findings")
            lines.append("")
            for cat in report.categories:
                emoji = _CATEGORY_EMOJI.get(cat.category_id, "📊")
                lines.append(f"### {emoji} {cat.category_name} ({cat.score:.1f}/10)")
                lines.append(f"*{cat.description}*")
                lines.append("")
                for check in cat.checks:
                    icon = _STATUS_ICON[check.status]
                    score_tag = f" ({check.raw_score:.0f}/10)" if check.raw_score is not None else ""
                    lines.append(f"- {icon} **{check.name}**{score_tag}: {check.message}")
                    if check.recommendation:
                        lines.append(f"  - 💡 {check.recommendation}")
                if cat.llm_insights:
                    lines.append("")
                    lines.append(f"> **LLM Insights:** {cat.llm_insights}")
                lines.append("")
        else:
            # Legacy flat dimension view
            lines.append("## Dimension Scores")
            lines.append("")
            lines.append("| Dimension | Score | Checks | Weight |")
            lines.append("|-----------|------:|-------:|-------:|")
            for dim in report.dimensions:
                lines.append(
                    f"| {dim.dimension_name} | {dim.score:.1f}/10 "
                    f"| {dim.passed_checks}/{dim.total_checks} | {dim.weight:.0f}% |"
                )
            lines.append("")

            # Persona doc readiness right after dimension scores
            lines.extend(MarkdownReporter._render_personas(report, show_cost=show_cost))

            lines.append("## Detailed Findings")
            lines.append("")
            for dim in report.dimensions:
                lines.append(f"### {dim.dimension_name}")
                lines.append("")
                for check in dim.checks:
                    icon = _STATUS_ICON[check.status]
                    lines.append(f"- {icon} **{check.name}**: {check.message}")
                    if check.recommendation:
                        lines.append(f"  - 💡 {check.recommendation}")
                if dim.llm_insights:
                    lines.append("")
                    lines.append(f"> **LLM Insights:** {dim.llm_insights}")
                lines.append("")

        # Recommendations
        recs = report.recommendations
        if recs:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(recs[:10], 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # LLM summary
        if report.llm_summary:
            lines.append("## LLM Summary")
            lines.append("")
            lines.append(report.llm_summary)
            lines.append("")

        return "\n".join(lines)


# ── Public entry point ───────────────────────────────────────────────


def format_report(
    report: Report,
    format: str = "terminal",
    verbose: bool = False,
    output_path: Any = None,
    show_cost: bool = False,
) -> str:
    """Format and optionally print the report.

    Returns the formatted string for json/markdown, an empty string for
    terminal (which prints directly via rich), or the saved file path for pdf.
    """
    if format == "json":
        return JSONReporter.render(report)

    if format == "markdown":
        return MarkdownReporter.render(report, show_cost=show_cost)

    if format == "pdf":
        from pathlib import Path

        from ai_readiness.core.pdf_reporter import render_pdf

        if output_path is None:
            raise ValueError("--output PATH is required when --format pdf is used.")
        md = MarkdownReporter.render(report, show_cost=show_cost)
        saved = render_pdf(md, Path(output_path))
        return f"PDF report saved to {saved}"

    # Default: terminal
    TerminalReporter(verbose=verbose, show_cost=show_cost).print(report)
    return ""
