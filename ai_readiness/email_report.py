"""HTML email report generator for AI Readiness scan results.

Generates a rich HTML email with:
- Overall score with color-coded rating
- Category score table with visual bars
- Top recommendations
- Per-repo summaries (for multi-repo scans)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _score_color(score: float) -> str:
    """Return hex color based on 0-100 score."""
    if score >= 80:
        return "#6c3fc5"  # Excellent — purple
    elif score >= 60:
        return "#22863a"  # Good — green
    elif score >= 40:
        return "#d29922"  # Fair — amber
    return "#cb2431"  # Poor — red


def _score_emoji(score: float) -> str:
    if score >= 80:
        return "🌟"
    elif score >= 60:
        return "🟢"
    elif score >= 40:
        return "🟡"
    return "🔴"


def _rating_text(score: float) -> str:
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Fair"
    return "Poor"


def _bar_html(score: float, max_score: float = 10.0, width_px: int = 150) -> str:
    """Render a score bar as inline HTML."""
    pct = min(100, (score / max_score) * 100)
    color = _score_color(score * 10)  # Convert 0-10 to 0-100 for color
    return (
        f'<div style="background:#e1e4e8;border-radius:4px;width:{width_px}px;height:16px;display:inline-block;vertical-align:middle;">'
        f'<div style="background:{color};border-radius:4px;height:16px;width:{pct:.0f}%;"></div>'
        f'</div>'
    )


_CATEGORY_EMOJI = {
    "ai_onboarding": "🚀",
    "ai_coding": "🤖",
    "repo_health": "🏥",
}


def generate_email_html(
    json_reports: list[dict[str, Any]],
    scan_date: str = "",
    target_agents: str = "",
    llm_enabled: bool = True,
    pipeline_url: str = "",
) -> str:
    """Generate a rich HTML email from one or more JSON scan reports.

    Args:
        json_reports: List of parsed JSON report dicts (from ai-readiness --format json)
        scan_date: Human-readable scan date
        target_agents: Comma-separated target agents
        llm_enabled: Whether LLM was used
        pipeline_url: Link to pipeline build results
    """
    sections: list[str] = []

    # Header
    sections.append(_email_header(scan_date, target_agents, llm_enabled, len(json_reports)))

    # Per-repo sections
    for report in json_reports:
        sections.append(_repo_section(report))

    # Footer
    sections.append(_email_footer(pipeline_url))

    body = "\n".join(sections)
    return _wrap_html(body)


def generate_email_from_files(report_dir: str | Path) -> str:
    """Generate HTML email from all JSON report files in a directory.

    Convenience function for pipeline scripts.
    """
    report_dir = Path(report_dir)
    json_files = sorted(report_dir.glob("*.json"))
    reports = []
    for jf in json_files:
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
                if "overall_score" in data:
                    reports.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return generate_email_html(reports)


def _email_header(scan_date: str, target_agents: str, llm_enabled: bool, repo_count: int) -> str:
    return f"""
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:32px;border-radius:12px 12px 0 0;">
      <h1 style="color:#fff;margin:0;font-size:28px;">📊 AI Readiness Scan Report</h1>
      <p style="color:#8b949e;margin:8px 0 0;">
        {f"Scanned {repo_count} repositor{'y' if repo_count == 1 else 'ies'}" }
        {f" · {scan_date}" if scan_date else ""}
      </p>
      <table style="margin-top:12px;color:#8b949e;font-size:13px;">
        <tr><td style="padding-right:16px;">Target Agents:</td><td style="color:#c9d1d9;">{target_agents or 'All'}</td></tr>
        <tr><td style="padding-right:16px;">LLM Analysis:</td><td style="color:#c9d1d9;">{'✅ Enabled' if llm_enabled else '❌ Disabled'}</td></tr>
      </table>
    </div>
    """


def _repo_section(report: dict[str, Any]) -> str:
    score = report.get("overall_score", 0)
    rating = report.get("rating", _rating_text(score))
    repo_path = report.get("repo_path", "Unknown")
    repo_name = repo_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    languages = ", ".join(report.get("languages", []))
    emoji = _score_emoji(score)
    color = _score_color(score)

    parts: list[str] = []

    # Repo header with score
    parts.append(f"""
    <div style="background:#fff;padding:24px;border:1px solid #d0d7de;margin-top:0;">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;">
        <div>
          <h2 style="margin:0;font-size:22px;color:#24292f;">{repo_name}</h2>
          <p style="color:#57606a;margin:4px 0 0;font-size:13px;">
            {repo_path}<br/>
            Languages: {languages or 'N/A'}
          </p>
        </div>
        <div style="text-align:center;padding:8px 20px;background:{color}15;border-radius:12px;border:2px solid {color};">
          <div style="font-size:36px;font-weight:bold;color:{color};">{emoji} {score:.0f}</div>
          <div style="font-size:13px;color:{color};font-weight:600;">/100 · {rating}</div>
        </div>
      </div>
    """)

    # Category scores table
    categories = report.get("categories", [])
    if categories:
        parts.append("""
      <table style="width:100%;border-collapse:collapse;margin-top:20px;font-size:14px;">
        <thead>
          <tr style="border-bottom:2px solid #d0d7de;">
            <th style="text-align:left;padding:8px 12px;color:#24292f;">Category</th>
            <th style="text-align:center;padding:8px 12px;color:#24292f;">Score</th>
            <th style="text-align:left;padding:8px 12px;color:#24292f;">Progress</th>
            <th style="text-align:center;padding:8px 12px;color:#24292f;">Checks</th>
            <th style="text-align:right;padding:8px 12px;color:#24292f;">Weight</th>
          </tr>
        </thead>
        <tbody>
        """)

        for cat in categories:
            cat_id = cat.get("id", "")
            cat_name = cat.get("name", "")
            cat_score = cat.get("score", 0)
            passed = cat.get("passed_checks", 0)
            total = cat.get("total_checks", 0)
            weight = cat.get("weight", 0)
            cat_emoji = _CATEGORY_EMOJI.get(cat_id, "📊")
            cat_color = _score_color(cat_score * 10)

            parts.append(f"""
          <tr style="border-bottom:1px solid #d0d7de;">
            <td style="padding:10px 12px;font-weight:600;">{cat_emoji} {cat_name}</td>
            <td style="text-align:center;padding:10px 12px;color:{cat_color};font-weight:bold;">{cat_score:.1f}/10</td>
            <td style="padding:10px 12px;">{_bar_html(cat_score)}</td>
            <td style="text-align:center;padding:10px 12px;color:#57606a;">{passed}/{total}</td>
            <td style="text-align:right;padding:10px 12px;color:#57606a;">{weight}%</td>
          </tr>
            """)

        parts.append("</tbody></table>")

    # Top recommendations
    recs = report.get("recommendations", [])
    if recs:
        parts.append("""
      <div style="margin-top:20px;padding:16px;background:#fff8c5;border-radius:8px;border:1px solid #d4a72c40;">
        <h3 style="margin:0 0 8px;font-size:15px;color:#9a6700;">💡 Top Recommendations</h3>
        <ol style="margin:0;padding-left:20px;color:#24292f;font-size:13px;line-height:1.8;">
        """)
        for rec in recs[:5]:
            parts.append(f"<li>{rec}</li>")
        parts.append("</ol></div>")

    # LLM summary
    llm_summary = report.get("llm_summary", "")
    if llm_summary:
        parts.append(f"""
      <div style="margin-top:16px;padding:16px;background:#ddf4ff;border-radius:8px;border:1px solid #54aeff40;">
        <h3 style="margin:0 0 8px;font-size:15px;color:#0969da;">🤖 AI Analysis</h3>
        <p style="margin:0;font-size:13px;color:#24292f;line-height:1.6;">{llm_summary}</p>
      </div>
        """)

    parts.append("</div>")
    return "\n".join(parts)


def _email_footer(pipeline_url: str) -> str:
    link = f'<a href="{pipeline_url}" style="color:#0969da;">View full reports in pipeline artifacts →</a>' if pipeline_url else ""
    return f"""
    <div style="background:#f6f8fa;padding:20px 24px;border-radius:0 0 12px 12px;border:1px solid #d0d7de;border-top:none;">
      <p style="margin:0;font-size:13px;color:#57606a;">
        {link}<br/>
        This is an automated report from the <strong>AI Readiness Tool</strong>.
      </p>
    </div>
    """


def _wrap_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:20px;background:#f6f8fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <div style="max-width:720px;margin:0 auto;">
    {body}
  </div>
</body>
</html>"""


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        html = generate_email_from_files(sys.argv[1])
        print(html)
    else:
        print("Usage: python -m ai_readiness.email_report <report_dir>")
