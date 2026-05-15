"""HTML email report for adoption metrics — designed for leadership sharing.

Generates a polished, executive-friendly HTML report showing:
- Key adoption KPIs (clones, views, forks, stars)
- Daily traffic trends with visual bars
- Top referral sources
- Call-to-action for other teams to try the tool
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ai_readiness.adoption.store import load_history


def generate_adoption_email(
    repo_root: Path,
    *,
    tool_repo_url: str = "",
    extra_cta_text: str = "",
) -> str:
    """Generate an HTML email report from stored adoption data."""
    history = load_history(repo_root)
    if not history.get("snapshots"):
        return "<p>No adoption data available yet.</p>"

    latest = history["snapshots"][-1]
    repo_name = history.get("repo", "AI Readiness Tool")
    report_date = datetime.utcnow().strftime("%B %d, %Y")

    sections: list[str] = []
    sections.append(_header(repo_name, report_date))
    sections.append(_kpi_cards(latest, history))
    sections.append(_traffic_chart(history))
    sections.append(_referrers_section(latest))
    sections.append(_trend_section(history))
    sections.append(_cta_section(tool_repo_url, extra_cta_text))
    sections.append(_footer())

    return _wrap_html("\n".join(sections))


# ── Header ────────────────────────────────────────────────────────────────────


def _header(repo_name: str, report_date: str) -> str:
    return f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161b22 50%,#1a1a2e 100%);
                padding:36px 32px;border-radius:16px 16px 0 0;">
      <h1 style="color:#fff;margin:0;font-size:28px;letter-spacing:-0.5px;">
        📊 AI Readiness Tool — Adoption Report
      </h1>
      <p style="color:#8b949e;margin:8px 0 0;font-size:15px;">
        {report_date} · {repo_name}
      </p>
    </div>
    """


# ── KPI Cards ─────────────────────────────────────────────────────────────────


def _kpi_cards(latest: dict, history: dict) -> str:
    clones = latest.get("clones", {})
    views = latest.get("views", {})

    # Calculate totals from all daily data (not just rolling window)
    all_clones = sum(d.get("count", 0) for d in history.get("daily_clones", []))
    all_views = sum(d.get("count", 0) for d in history.get("daily_views", []))
    all_unique_clones = sum(d.get("uniques", 0) for d in history.get("daily_clones", []))

    cards = [
        _kpi_card(
            "👥 Unique Users",
            str(all_unique_clones),
            "Distinct people who cloned the tool",
            "#58a6ff",
        ),
        _kpi_card(
            "📥 Total Clones",
            str(all_clones),
            "Times the repo was cloned",
            "#3fb950",
        ),
        _kpi_card(
            "👀 Page Views",
            str(all_views),
            "Total page views on GitHub",
            "#d29922",
        ),
        _kpi_card(
            "⭐ Stars / 🍴 Forks",
            f"{latest.get('stars', 0)} / {latest.get('forks_count', 0)}",
            "Community engagement",
            "#bc8cff",
        ),
    ]

    return f"""
    <div style="background:#fff;padding:24px 24px 8px;border:1px solid #d0d7de;border-top:none;">
      <h2 style="margin:0 0 16px;font-size:18px;color:#24292f;">Key Metrics</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr>{''.join(cards)}</tr>
      </table>
    </div>
    """


def _kpi_card(title: str, value: str, subtitle: str, color: str) -> str:
    return f"""
    <td style="width:25%;padding:8px;vertical-align:top;">
      <div style="background:{color}10;border:1px solid {color}30;border-radius:12px;
                  padding:20px 16px;text-align:center;">
        <div style="font-size:13px;color:#57606a;font-weight:600;">{title}</div>
        <div style="font-size:32px;font-weight:bold;color:{color};margin:8px 0 4px;">
          {value}
        </div>
        <div style="font-size:11px;color:#8b949e;">{subtitle}</div>
      </div>
    </td>
    """


# ── Helpers ───────────────────────────────────────────────────────────────────


def _aggregate_weekly(history: dict) -> list[dict]:
    """Aggregate daily clone/view data into ISO-week buckets."""
    daily_clones = history.get("daily_clones", [])
    daily_views = history.get("daily_views", [])

    dates: dict[str, dict] = {}
    for d in daily_clones:
        dt = d["timestamp"][:10]
        dates.setdefault(dt, {})["clones"] = d.get("count", 0)
        dates[dt]["u_clones"] = d.get("uniques", 0)
    for d in daily_views:
        dt = d["timestamp"][:10]
        dates.setdefault(dt, {})["views"] = d.get("count", 0)
        dates[dt]["u_views"] = d.get("uniques", 0)

    weeks: dict[str, dict] = {}
    for dt_str in sorted(dates):
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
        except ValueError:
            continue
        # Monday-based week start
        week_start = dt - timedelta(days=dt.weekday())
        week_key = week_start.strftime("%Y-%m-%d")
        week_end = week_start + timedelta(days=6)

        bucket = weeks.setdefault(week_key, {
            "week_start": week_start,
            "week_end": week_end,
            "clones": 0, "u_clones": 0, "views": 0, "u_views": 0,
        })
        row = dates[dt_str]
        bucket["clones"] += row.get("clones", 0)
        bucket["u_clones"] += row.get("u_clones", 0)
        bucket["views"] += row.get("views", 0)
        bucket["u_views"] += row.get("u_views", 0)

    return [weeks[k] for k in sorted(weeks)]


# ── SVG Time Chart ────────────────────────────────────────────────────────────


def _traffic_chart(history: dict) -> str:
    weeks = _aggregate_weekly(history)
    if not weeks:
        return ""

    display_weeks = weeks[-12:]  # Show up to 12 weeks
    n = len(display_weeks)

    # Chart dimensions
    chart_w = 660
    chart_h = 240
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b

    max_val = max(
        max((w["views"] for w in display_weeks), default=1),
        max((w["clones"] for w in display_weeks), default=1),
    ) or 1
    # Round up to a nice number for gridlines
    grid_step = _nice_step(max_val)
    max_y = ((max_val // grid_step) + 1) * grid_step

    bar_group_w = plot_w / n
    bar_w = max(bar_group_w * 0.3, 6)
    gap = max(bar_w * 0.3, 3)

    svg_parts: list[str] = []

    # Gradient definitions
    svg_parts.append(f"""
    <defs>
      <linearGradient id="viewsGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#58a6ff"/>
        <stop offset="100%" stop-color="#388bfd"/>
      </linearGradient>
      <linearGradient id="clonesGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#3fb950"/>
        <stop offset="100%" stop-color="#2ea043"/>
      </linearGradient>
    </defs>
    """)

    # Gridlines and Y-axis labels
    for i in range(int(max_y // grid_step) + 1):
        val = i * grid_step
        y = pad_t + plot_h - (val / max_y) * plot_h
        svg_parts.append(
            f'<line x1="{pad_l}" y1="{y}" x2="{pad_l + plot_w}" y2="{y}" '
            f'stroke="#e1e4e8" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{pad_l - 8}" y="{y + 4}" text-anchor="end" '
            f'font-size="11" fill="#8b949e" font-family="sans-serif">{int(val)}</text>'
        )

    # Bars and X-axis labels
    for i, w in enumerate(display_weeks):
        cx = pad_l + (i + 0.5) * bar_group_w

        # Views bar
        v_h = (w["views"] / max_y) * plot_h if max_y else 0
        v_x = cx - bar_w - gap / 2
        v_y = pad_t + plot_h - v_h
        svg_parts.append(
            f'<rect x="{v_x:.1f}" y="{v_y:.1f}" width="{bar_w:.1f}" height="{v_h:.1f}" '
            f'rx="3" fill="url(#viewsGrad)" opacity="0.9"/>'
        )
        # Value label on top of views bar
        if w["views"] > 0:
            svg_parts.append(
                f'<text x="{v_x + bar_w / 2:.1f}" y="{v_y - 4:.1f}" text-anchor="middle" '
                f'font-size="10" fill="#388bfd" font-family="sans-serif" font-weight="bold">'
                f'{w["views"]}</text>'
            )

        # Clones bar
        c_h = (w["clones"] / max_y) * plot_h if max_y else 0
        c_x = cx + gap / 2
        c_y = pad_t + plot_h - c_h
        svg_parts.append(
            f'<rect x="{c_x:.1f}" y="{c_y:.1f}" width="{bar_w:.1f}" height="{c_h:.1f}" '
            f'rx="3" fill="url(#clonesGrad)" opacity="0.9"/>'
        )
        if w["clones"] > 0:
            svg_parts.append(
                f'<text x="{c_x + bar_w / 2:.1f}" y="{c_y - 4:.1f}" text-anchor="middle" '
                f'font-size="10" fill="#2ea043" font-family="sans-serif" font-weight="bold">'
                f'{w["clones"]}</text>'
            )

        # X-axis label
        label = w["week_start"].strftime("%b %d")
        label_y = pad_t + plot_h + 16
        svg_parts.append(
            f'<text x="{cx:.1f}" y="{label_y}" text-anchor="middle" '
            f'font-size="10" fill="#57606a" font-family="sans-serif">{label}</text>'
        )

    # Baseline
    svg_parts.append(
        f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" '
        f'y2="{pad_t + plot_h}" stroke="#d0d7de" stroke-width="1.5"/>'
    )

    # Legend
    legend_y = chart_h + 8
    svg_parts.append(
        f'<rect x="{pad_l}" y="{legend_y}" width="12" height="12" rx="2" fill="url(#viewsGrad)"/>'
        f'<text x="{pad_l + 16}" y="{legend_y + 10}" font-size="11" fill="#57606a" '
        f'font-family="sans-serif">Views</text>'
        f'<rect x="{pad_l + 80}" y="{legend_y}" width="12" height="12" rx="2" fill="url(#clonesGrad)"/>'
        f'<text x="{pad_l + 96}" y="{legend_y + 10}" font-size="11" fill="#57606a" '
        f'font-family="sans-serif">Clones</text>'
    )

    svg_h = chart_h + 30
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {chart_w} {svg_h}" '
        f'width="{chart_w}" height="{svg_h}" style="display:block;margin:0 auto;">'
        + "\n".join(svg_parts)
        + "</svg>"
    )

    return f"""
    <div style="background:#fff;padding:24px;border:1px solid #d0d7de;border-top:none;">
      <h2 style="margin:0 0 16px;font-size:18px;color:#24292f;">📈 Weekly Traffic</h2>
      {svg}
    </div>
    """


def _nice_step(max_val: int | float) -> int:
    """Pick a human-friendly grid step for the Y axis."""
    if max_val <= 5:
        return 1
    if max_val <= 15:
        return 5
    if max_val <= 50:
        return 10
    if max_val <= 150:
        return 25
    if max_val <= 500:
        return 50
    return 100


# ── Referrers ─────────────────────────────────────────────────────────────────


def _referrers_section(latest: dict) -> str:
    referrers = latest.get("top_referrers", [])
    if not referrers:
        return ""

    rows = []
    for r in referrers:
        rows.append(f"""
        <tr style="border-bottom:1px solid #d0d7de;">
          <td style="padding:10px 12px;font-size:14px;color:#24292f;">{r['name']}</td>
          <td style="padding:10px 12px;text-align:center;font-weight:bold;color:#0969da;">
            {r['views']}
          </td>
          <td style="padding:10px 12px;text-align:center;color:#57606a;">
            {r['unique']}
          </td>
        </tr>
        """)

    return f"""
    <div style="background:#fff;padding:24px;border:1px solid #d0d7de;border-top:none;">
      <h2 style="margin:0 0 16px;font-size:18px;color:#24292f;">🔗 Where People Find Us</h2>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="border-bottom:2px solid #d0d7de;">
            <th style="text-align:left;padding:8px 12px;font-size:13px;color:#57606a;">Source</th>
            <th style="text-align:center;padding:8px 12px;font-size:13px;color:#57606a;">Views</th>
            <th style="text-align:center;padding:8px 12px;font-size:13px;color:#57606a;">Unique Visitors</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


# ── Trend Section ─────────────────────────────────────────────────────────────


def _trend_section(history: dict) -> str:
    weeks = _aggregate_weekly(history)
    if len(weeks) < 2:
        return ""

    rows = []
    prev_views = None
    for w in weeks[-8:]:
        label = f"{w['week_start'].strftime('%b %d')} – {w['week_end'].strftime('%b %d')}"

        # Week-over-week change indicator
        if prev_views is not None and prev_views > 0:
            delta = ((w["views"] - prev_views) / prev_views) * 100
            if delta > 0:
                trend_badge = f'<span style="color:#3fb950;font-size:11px;">▲ {delta:.0f}%</span>'
            elif delta < 0:
                trend_badge = f'<span style="color:#cb2431;font-size:11px;">▼ {abs(delta):.0f}%</span>'
            else:
                trend_badge = '<span style="color:#8b949e;font-size:11px;">—</span>'
        else:
            trend_badge = ""
        prev_views = w["views"]

        rows.append(f"""
        <tr style="border-bottom:1px solid #d0d7de;">
          <td style="padding:8px 12px;font-size:13px;color:#57606a;">{label}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;font-weight:600;">{w['u_clones']}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;">{w['clones']}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;">{w['u_views']}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;">{w['views']}</td>
          <td style="text-align:center;padding:8px 12px;">{trend_badge}</td>
        </tr>
        """)

    return f"""
    <div style="background:#fff;padding:24px;border:1px solid #d0d7de;border-top:none;">
      <h2 style="margin:0 0 16px;font-size:18px;color:#24292f;">📊 Weekly Trend</h2>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="border-bottom:2px solid #d0d7de;">
            <th style="text-align:left;padding:8px 12px;font-size:13px;color:#57606a;">Week</th>
            <th style="text-align:center;padding:8px 12px;font-size:13px;color:#57606a;">Unique Cloners</th>
            <th style="text-align:center;padding:8px 12px;font-size:13px;color:#57606a;">Total Clones</th>
            <th style="text-align:center;padding:8px 12px;font-size:13px;color:#57606a;">Unique Viewers</th>
            <th style="text-align:center;padding:8px 12px;font-size:13px;color:#57606a;">Total Views</th>
            <th style="text-align:center;padding:8px 12px;font-size:13px;color:#57606a;">WoW</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


# ── Call to Action ────────────────────────────────────────────────────────────


def _cta_section(tool_repo_url: str, extra_text: str) -> str:
    repo_link = tool_repo_url or "https://github.com/koushikmakam-MS/AI_Readiness_Tool"

    extra_html = f'<p style="margin:12px 0 0;font-size:14px;color:#24292f;">{extra_text}</p>' if extra_text else ""

    return f"""
    <div style="background:linear-gradient(135deg,#ddf4ff 0%,#d4f4dd 100%);
                padding:28px 24px;border:1px solid #54aeff40;border-top:none;">
      <h2 style="margin:0 0 12px;font-size:20px;color:#0969da;">
        🚀 Try the AI Readiness Tool on Your Repo
      </h2>
      <p style="margin:0;font-size:14px;color:#24292f;line-height:1.7;">
        The <strong>AI Readiness Tool</strong> assesses how well your repository is prepared
        for AI coding agents like Copilot, Cursor, and Claude. Get a score from 0–100 with
        actionable recommendations to improve your repo's AI-friendliness.
      </p>
      {extra_html}
      <div style="margin-top:20px;">
        <a href="{repo_link}"
           style="display:inline-block;padding:12px 28px;background:#0969da;color:#fff;
                  text-decoration:none;border-radius:8px;font-weight:bold;font-size:14px;">
          Get Started →
        </a>
        <span style="display:inline-block;margin-left:16px;padding:12px 20px;
                     background:#fff;border:1px solid #d0d7de;border-radius:8px;
                     font-family:monospace;font-size:13px;color:#24292f;">
          pip install -e . &amp;&amp; ai-readiness check .
        </span>
      </div>
      <p style="margin:16px 0 0;font-size:12px;color:#57606a;">
        ✅ Read-only — never modifies your repo &nbsp;·&nbsp;
        ✅ Works with any language &nbsp;·&nbsp;
        ✅ 5 min setup
      </p>
    </div>
    """


# ── Footer ────────────────────────────────────────────────────────────────────


def _footer() -> str:
    return """
    <div style="background:#f6f8fa;padding:20px 24px;border-radius:0 0 16px 16px;
                border:1px solid #d0d7de;border-top:none;text-align:center;">
      <p style="margin:0;font-size:12px;color:#8b949e;">
        Generated by the AI Readiness Tool · Adoption Tracker<br/>
        Data sourced from GitHub Traffic API
      </p>
    </div>
    """


# ── Wrapper ───────────────────────────────────────────────────────────────────


def _wrap_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Readiness Tool — Adoption Report</title>
</head>
<body style="margin:0;padding:24px;background:#f0f2f5;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <div style="max-width:720px;margin:0 auto;">
    {body}
  </div>
</body>
</html>"""
