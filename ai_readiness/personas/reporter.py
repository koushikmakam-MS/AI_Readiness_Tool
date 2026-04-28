"""Reporter for persona run results."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from ai_readiness.personas.base import DIMENSION_LABELS, Dimension
from ai_readiness.personas.runner import RunReport


def render_terminal(report: RunReport, console: Console, *, verbose: bool = False, show_cost: bool = False) -> None:
    if report.dry_run:
        console.print("[bold cyan]Persona Run — DRY RUN[/bold cyan]")
        cost_part = f"  Estimated cost: [yellow]${report.overall.total_cost_usd:.4f}[/yellow]" if show_cost else ""
        console.print(
            f"Docs: {report.docs_total}  Chunks: {report.chunks_total}"
            f"{cost_part}"
        )
        return

    console.print("[bold cyan]Persona Documentation Readiness[/bold cyan]")
    cost_part = f"  Cost: ${report.overall.total_cost_usd:.4f}" if show_cost else ""
    console.print(
        f"Docs: {report.docs_total}  Chunks: {report.chunks_total}  "
        f"Overall: [bold]{report.overall.overall_score}/100[/bold]"
        f"{cost_part}"
    )
    if report.aborted_reason:
        console.print(f"[yellow]Aborted: {report.aborted_reason}[/yellow]")

    persona_table = Table(title="Per-Persona Scores")
    persona_table.add_column("Persona", style="cyan")
    persona_table.add_column("Display", style="dim")
    persona_table.add_column("Score", justify="right")
    persona_table.add_column("Docs", justify="right")
    if show_cost:
        persona_table.add_column("Cost $", justify="right")
    for r in report.persona_results:
        row = [
            r.persona_id,
            r.display_name,
            f"{r.overall_score:.1f}",
            str(r.docs_scored),
        ]
        if show_cost:
            row.append(f"{r.estimated_cost_usd:.4f}")
        persona_table.add_row(*row)
    console.print(persona_table)

    dim_table = Table(title="Dimension Averages (1-5)")
    dim_table.add_column("Dimension", style="cyan")
    dim_table.add_column("Score", justify="right")
    for dim in Dimension:
        dim_table.add_row(
            DIMENSION_LABELS[dim], f"{report.overall.per_dimension.get(dim, 0.0):.2f}"
        )
    console.print(dim_table)

    if verbose:
        for r in report.persona_results:
            console.print(f"\n[bold]{r.display_name}[/bold] — top suggestions:")
            seen: set[str] = set()
            for rs in sorted(r.rubric_scores, key=lambda s: s.average)[:5]:
                for sug in rs.suggestions[:2]:
                    if sug in seen:
                        continue
                    seen.add(sug)
                    console.print(f"  - {rs.relative_path}: {sug}")


def to_json(report: RunReport) -> str:
    payload: dict[str, Any] = {
        "dry_run": report.dry_run,
        "aborted_reason": report.aborted_reason,
        "docs_total": report.docs_total,
        "chunks_total": report.chunks_total,
        "overall": {
            "score": report.overall.overall_score,
            "per_persona": report.overall.per_persona,
            "per_dimension": {
                d.value: v for d, v in report.overall.per_dimension.items()
            },
            "weights_used": report.overall.weights_used,
            "total_cost_usd": report.overall.total_cost_usd,
            "total_prompt_tokens": report.overall.total_prompt_tokens,
            "total_completion_tokens": report.overall.total_completion_tokens,
            "total_embedding_tokens": report.overall.total_embedding_tokens,
        },
        "personas": [],
    }
    for r in report.persona_results:
        payload["personas"].append(
            {
                "persona_id": r.persona_id,
                "display_name": r.display_name,
                "overall_score": r.overall_score,
                "docs_considered": r.docs_considered,
                "docs_scored": r.docs_scored,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "embedding_tokens": r.embedding_tokens,
                "estimated_cost_usd": r.estimated_cost_usd,
                "dimension_averages": {
                    d.value: v for d, v in r.dimension_averages.items()
                },
                "task_result": (
                    {
                        "task": r.task_result.task,
                        "answer": r.task_result.answer,
                        "score": r.task_result.score,
                        "missing_info": r.task_result.missing_info,
                    }
                    if r.task_result
                    else None
                ),
                "scores": [
                    {
                        "chunk_id": s.chunk_id,
                        "relative_path": s.relative_path,
                        "scores": {d.value: v for d, v in s.scores.items()},
                        "justification": s.justification,
                        "suggestions": s.suggestions,
                    }
                    for s in r.rubric_scores
                ],
            }
        )
    return json.dumps(payload, indent=2)


def to_markdown(report: RunReport, *, show_cost: bool = False) -> str:
    lines: list[str] = ["# Persona Documentation Readiness Report", ""]
    lines.append(f"- Docs analysed: **{report.docs_total}**")
    lines.append(f"- Chunks scored: **{report.chunks_total}**")
    lines.append(f"- Overall score: **{report.overall.overall_score}/100**")
    if show_cost:
        lines.append(f"- Estimated cost: **${report.overall.total_cost_usd:.4f}**")
    if report.aborted_reason:
        lines.append(f"- ⚠️ Aborted: {report.aborted_reason}")
    lines.append("")

    # -- Persona overview table (with roles) at the top --
    lines.append("## Meet the Personas")
    lines.append("")
    lines.append(
        "Each persona represents a different AI agent role. They evaluate your "
        "documentation from their unique perspective — asking whether the docs "
        "give them enough context to do their job without hallucinating."
    )
    lines.append("")
    if show_cost:
        lines.append("| Persona | Role | Score (/100) | Docs scored | Cost (USD) |")
        lines.append("|---------|------|-------------:|------------:|-----------:|")
    else:
        lines.append("| Persona | Role | Score (/100) | Docs scored |")
        lines.append("|---------|------|-------------:|------------:|")
    for r in report.persona_results:
        role = r.role or "—"
        row = f"| {r.display_name} (`{r.persona_id}`) | {role} | {r.overall_score:.1f}/100 | {r.docs_scored} "
        if show_cost:
            row += f"| {r.estimated_cost_usd:.4f} |"
        else:
            row += "|"
        lines.append(row)
    lines.append("")

    # -- Rubric explanation --
    lines.append("## How Scores Work")
    lines.append("")
    lines.append(
        "Every doc is scored on three dimensions (1–5 each):"
    )
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

    # -- Dimension averages --
    lines.append("## Dimension averages (1-5)")
    lines.append("")
    for dim in Dimension:
        lines.append(
            f"- **{DIMENSION_LABELS[dim]}**: "
            f"{report.overall.per_dimension.get(dim, 0.0):.2f}"
        )
    lines.append("")

    # -- Per-persona improvement details --
    for r in report.persona_results:
        lines.append(f"## {r.display_name} — improvements")
        lines.append("")
        if not r.rubric_scores:
            lines.append("_No scored docs._\n")
            continue
        for rs in sorted(r.rubric_scores, key=lambda s: s.average)[:5]:
            lines.append(f"### `{rs.relative_path}`  (avg {rs.average:.2f})")
            if rs.justification:
                lines.append(f"> {rs.justification}")
            for sug in rs.suggestions:
                lines.append(f"- {sug}")
            lines.append("")
        if r.task_result:
            lines.append(f"**Simulated task score:** {r.task_result.score:.1f}/10")
            if r.task_result.missing_info:
                lines.append("Missing info reported by persona:")
                for m in r.task_result.missing_info:
                    lines.append(f"- {m}")
            lines.append("")
    return "\n".join(lines)
