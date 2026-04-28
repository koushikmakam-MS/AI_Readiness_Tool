"""Reporter for persona run results."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from ai_readiness.personas.base import DIMENSION_LABELS, Dimension
from ai_readiness.personas.runner import RunReport


def render_terminal(report: RunReport, console: Console, *, verbose: bool = False) -> None:
    if report.dry_run:
        console.print("[bold cyan]Persona Run — DRY RUN[/bold cyan]")
        console.print(
            f"Docs: {report.docs_total}  Chunks: {report.chunks_total}  "
            f"Estimated cost: [yellow]${report.overall.total_cost_usd:.4f}[/yellow]"
        )
        return

    console.print("[bold cyan]Persona Documentation Readiness[/bold cyan]")
    console.print(
        f"Docs: {report.docs_total}  Chunks: {report.chunks_total}  "
        f"Overall: [bold]{report.overall.overall_score}/100[/bold]  "
        f"Cost: ${report.overall.total_cost_usd:.4f}"
    )
    if report.aborted_reason:
        console.print(f"[yellow]Aborted: {report.aborted_reason}[/yellow]")

    persona_table = Table(title="Per-Persona Scores")
    persona_table.add_column("Persona", style="cyan")
    persona_table.add_column("Display", style="dim")
    persona_table.add_column("Score", justify="right")
    persona_table.add_column("Docs", justify="right")
    persona_table.add_column("Cost $", justify="right")
    for r in report.persona_results:
        persona_table.add_row(
            r.persona_id,
            r.display_name,
            f"{r.overall_score:.1f}",
            str(r.docs_scored),
            f"{r.estimated_cost_usd:.4f}",
        )
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


def to_markdown(report: RunReport) -> str:
    lines: list[str] = ["# Persona Documentation Readiness Report", ""]
    lines.append(f"- Docs analysed: **{report.docs_total}**")
    lines.append(f"- Chunks scored: **{report.chunks_total}**")
    lines.append(f"- Overall score: **{report.overall.overall_score}/100**")
    lines.append(f"- Estimated cost: **${report.overall.total_cost_usd:.4f}**")
    if report.aborted_reason:
        lines.append(f"- ⚠️ Aborted: {report.aborted_reason}")
    lines.append("")
    lines.append("## Per-persona scores")
    lines.append("")
    lines.append("| Persona | Display | Score | Docs scored | Cost (USD) |")
    lines.append("|---|---|---:|---:|---:|")
    for r in report.persona_results:
        lines.append(
            f"| `{r.persona_id}` | {r.display_name} | {r.overall_score:.1f} | "
            f"{r.docs_scored} | {r.estimated_cost_usd:.4f} |"
        )
    lines.append("")
    lines.append("## Dimension averages (1-5)")
    lines.append("")
    for dim in Dimension:
        lines.append(
            f"- **{DIMENSION_LABELS[dim]}**: "
            f"{report.overall.per_dimension.get(dim, 0.0):.2f}"
        )
    lines.append("")
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
