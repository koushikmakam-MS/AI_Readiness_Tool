"""HTML email report for adoption metrics — designed for leadership sharing.

Generates a polished, executive-friendly HTML report showing:
- Key adoption KPIs (clones, views, forks, stars)
- Daily traffic trends with visual bars
- Top referral sources
- Call-to-action for other teams to try the tool
"""

from __future__ import annotations

from datetime import datetime
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


# ── Traffic Chart ─────────────────────────────────────────────────────────────


def _traffic_chart(history: dict) -> str:
    daily_clones = history.get("daily_clones", [])
    daily_views = history.get("daily_views", [])

    if not daily_clones and not daily_views:
        return ""

    # Merge into date map
    dates: dict[str, dict] = {}
    for d in daily_clones:
        dt = d["timestamp"][:10]
        dates.setdefault(dt, {})["clones"] = d.get("count", 0)
        dates[dt]["u_clones"] = d.get("uniques", 0)
    for d in daily_views:
        dt = d["timestamp"][:10]
        dates.setdefault(dt, {})["views"] = d.get("count", 0)
        dates[dt]["u_views"] = d.get("uniques", 0)

    sorted_dates = sorted(dates.keys())[-14:]
    max_views = max((dates[d].get("views", 0) for d in sorted_dates), default=1) or 1

    rows = []
    for dt in sorted_dates:
        row = dates[dt]
        c = row.get("clones", 0)
        v = row.get("views", 0)
        bar_pct = min(100, (v / max_views) * 100)

        # Format date nicely
        try:
            nice_date = datetime.strptime(dt, "%Y-%m-%d").strftime("%b %d")
        except ValueError:
            nice_date = dt

        rows.append(f"""
        <tr>
          <td style="padding:4px 12px;font-size:12px;color:#57606a;white-space:nowrap;">{nice_date}</td>
          <td style="padding:4px 8px;width:60%;">
            <div style="display:flex;align-items:center;gap:8px;">
              <div style="background:linear-gradient(90deg,#58a6ff,#3fb950);height:18px;
                          border-radius:4px;width:{max(bar_pct, 2):.0f}%;min-width:4px;"></div>
              <span style="font-size:11px;color:#57606a;">{v} views</span>
            </div>
          </td>
          <td style="padding:4px 8px;text-align:center;font-size:12px;color:#24292f;font-weight:600;">
            {c} clone{'s' if c != 1 else ''}
          </td>
        </tr>
        """)

    return f"""
    <div style="background:#fff;padding:24px;border:1px solid #d0d7de;border-top:none;">
      <h2 style="margin:0 0 16px;font-size:18px;color:#24292f;">📈 Daily Traffic</h2>
      <table style="width:100%;border-collapse:collapse;">
        {''.join(rows)}
      </table>
    </div>
    """


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
    snapshots = history.get("snapshots", [])
    if len(snapshots) < 2:
        return ""

    rows = []
    for snap in snapshots[-8:]:
        ts = snap.get("timestamp", "")
        try:
            nice_date = datetime.fromisoformat(ts).strftime("%b %d, %Y")
        except (ValueError, TypeError):
            nice_date = ts[:10]

        c = snap.get("clones", {})
        v = snap.get("views", {})
        rows.append(f"""
        <tr style="border-bottom:1px solid #d0d7de;">
          <td style="padding:8px 12px;font-size:13px;color:#57606a;">{nice_date}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;">{c.get('unique', 0)}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;">{c.get('total', 0)}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;">{v.get('unique', 0)}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;">{v.get('total', 0)}</td>
          <td style="text-align:center;padding:8px 12px;font-size:13px;">{snap.get('stars', 0)}</td>
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
            <th style="text-align:center;padding:8px 12px;font-size:13px;color:#57606a;">Stars</th>
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
