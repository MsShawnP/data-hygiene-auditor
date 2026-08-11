"""HTML report generator."""

from __future__ import annotations

import base64
import json
from html import escape as _html_escape
from pathlib import Path
from typing import Any

from ..core import (
    KNOWN_ISSUE_TYPES,
    count_issues,
    issue_headline,
    score_band,
    score_label,
)
from . import palette as P

_FONTS_DIR = Path(__file__).parent / "fonts"

# Band -> colour/description maps for the report. Keyed by the band name from
# core.score_band so the thresholds are defined in exactly one place.
_OVERALL_COLORS = {
    'clean': 'var(--hk-35)',
    'attention': 'var(--sg-55)',
    'significant': 'var(--accent)',
    'critical': 'var(--accent)',
}
_OVERALL_DESC = {
    'clean': 'This dataset is in good shape.',
    'attention': 'Several issues should be addressed before use.',
    'significant': 'This dataset has serious quality problems.',
    'critical': 'This dataset has serious quality problems.',
}
_SHEET_COLORS = {
    'clean': 'var(--low)',
    'attention': 'var(--medium)',
    'significant': 'var(--high)',
    'critical': 'var(--high)',
}


def _font_face_css() -> str:
    """Return @font-face rules with base64-embedded woff2 fonts."""
    blocks: list[str] = []
    for name, css_family, weight in [
        ("playfair-display-latin.woff2", "Playfair Display", "400 700"),
        ("source-sans-3-latin.woff2", "Source Sans 3", "400 700"),
    ]:
        path = _FONTS_DIR / name
        if not path.exists():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        blocks.append(
            f"@font-face {{\n"
            f"  font-family: '{css_family}';\n"
            f"  font-style: normal;\n"
            f"  font-weight: {weight};\n"
            f"  font-display: swap;\n"
            f"  src: url('data:font/woff2;base64,{b64}') format('woff2');\n"
            f"}}"
        )
    return "\n".join(blocks)


def _h(val: object) -> str:
    """Escape a value for safe inclusion in HTML text or attributes."""
    return _html_escape(str(val), quote=True)


def _render_fix(fix: dict[str, str]) -> str:
    """Render a fix suggestion as an HTML code block with copy button."""
    desc = _h(fix.get('description', ''))
    code = _h(fix.get('code', ''))
    strategy = _h(fix.get('strategy', 'fix'))
    return (
        '<div class="fix-block">'
        '<div class="fix-header">'
        f'<span>Suggested Fix ({strategy})</span>'
        '<button class="fix-copy"'
        ' onclick="copyFix(this)">Copy</button>'
        '</div>'
        f'<div class="fix-desc">{desc}</div>'
        f'<pre class="fix-code">{code}</pre>'
        '</div>'
    )


# Static one-liner lifted out of the score-hero f-string so no source line exceeds
# the 120-char lint limit; implicit concatenation reproduces the exact same markup.
_SCORE_SCALE_HTML = (
    '<div class="score-scale">Health score, 0&ndash;100 &mdash; '
    '90+ clean &middot; 70&ndash;89 needs attention &middot; '
    '40&ndash;69 significant issues &middot; below 40 critical</div>'
)


def generate_html(results: dict[str, Any], output_path: str) -> str:
    """Generate a client-readable HTML report."""
    counts = count_issues(results)
    total_issues = counts.get('total', 0)
    severity_totals = counts

    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Data Hygiene Audit — {_h(results['input_file'])}</title>
<style>
{_font_face_css()}
:root {{
    --canvas: {P.CANVAS};
    --card: #ffffff;
    --card-border: {P.LONDON_85};
    --text: {P.LONDON_20};
    --text-muted: {P.LONDON_35};
    --ink: {P.INK};
    --accent: {P.RED_42};
    --chicago: {P.CHICAGO_20};
    --chicago-95: {P.CHICAGO_95};
    --chicago-85: {P.CHICAGO_85};
    --hk-35: {P.HONG_KONG_35};
    --hk-95: {P.HONG_KONG_95};
    --tokyo-40: {P.TOKYO_40};
    --sg-55: {P.SINGAPORE_55};
    --sg-95: {P.SINGAPORE_95};
    --red-95: {P.RED_95};
    --high: {P.SEV_HIGH};
    --medium: {P.SEV_MEDIUM};
    --low: {P.SEV_LOW};
    --info: {P.CHICAGO_20};
    --serif: {P.FONT_SERIF};
    --sans: {P.FONT_SANS};
    --radius: {P.BORDER_RADIUS};
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: var(--sans);
    background: var(--canvas);
    color: var(--text);
    line-height: 1.6;
    padding: 48px 24px;
    max-width: 900px;
    margin: 0 auto;
}}
h1 {{
    font-family: var(--serif);
    color: var(--ink);
    font-size: 1.8rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}}
h2 {{
    font-family: var(--serif);
    color: var(--ink);
    font-size: 1.4rem;
    font-weight: 700;
    margin: 2rem 0 1rem;
    border-bottom: 1px solid var(--card-border);
    padding-bottom: 0.5rem;
}}
h3 {{
    font-family: var(--serif);
    color: var(--ink);
    font-size: 1.1rem;
    font-weight: 700;
    margin: 1.5rem 0 0.5rem;
}}
.subtitle {{
    color: var(--text-muted); font-size: 0.95rem; margin-bottom: 1.5rem;
}}
.summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin: 1.5rem 0;
}}
.summary-card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1.2rem;
    text-align: center;
}}
.summary-card .number {{
    font-family: var(--serif);
    font-size: 2rem;
    font-weight: 700;
}}
.summary-card .label {{
    font-family: var(--sans);
    color: var(--text-muted); font-size: 0.85rem;
    text-transform: uppercase; letter-spacing: 0.04em;
}}
.high .number {{ color: var(--high); }}
.medium .number {{ color: var(--medium); }}
.low .number {{ color: var(--low); }}
.info .number {{ color: var(--info); }}
.field-card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1.2rem;
    margin-bottom: 1rem;
}}
.field-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}}
.field-name {{ font-weight: 600; font-size: 1.05rem; }}
.field-type {{
    background: var(--chicago-95);
    color: var(--chicago);
    padding: 0.2rem 0.6rem;
    border-radius: var(--radius);
    font-size: 0.8rem;
    font-weight: 500;
}}
.null-bar {{
    height: 6px;
    background: #e0e0e0;
    border-radius: var(--radius);
    margin: 0.5rem 0;
    overflow: hidden;
}}
.null-bar-fill {{
    height: 100%;
    border-radius: var(--radius);
    transition: width 0.2s ease-out;
}}
.issue {{
    border-left: 3px solid var(--card-border);
    padding: 0.75rem 1rem;
    margin: 0.75rem 0;
    background: var(--card);
    border-radius: 0 var(--radius) var(--radius) 0;
}}
.issue.severity-High {{ border-left-color: var(--high); }}
.issue.severity-Medium {{ border-left-color: var(--medium); }}
.issue.severity-Low {{ border-left-color: var(--low); }}
.severity-badge {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: var(--radius);
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
.severity-badge.High {{ background: var(--high); color: #fff; }}
.severity-badge.Medium {{ background: var(--medium); color: #fff; }}
.severity-badge.Low {{ background: var(--low); color: #fff; }}
.why-box {{
    margin-top: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: var(--chicago-95);
    border-left: 3px solid var(--chicago-85);
    border-radius: 0 var(--radius) var(--radius) 0;
    font-size: 0.9rem;
    color: var(--text-muted);
}}
.why-box strong {{ color: var(--chicago); }}
.format-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0;
    font-size: 0.9rem;
}}
.format-table th {{
    text-align: left;
    padding: 0.4rem 0.75rem;
    background: var(--chicago);
    color: #fff;
    font-weight: 600;
    font-size: 0.8rem;
}}
.format-table td {{
    text-align: left;
    padding: 0.4rem 0.75rem;
    border-bottom: 1px solid #e0e0e0;
}}
.format-table tr:nth-child(even) td {{ background: var(--canvas); }}
.dup-group {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1rem;
    margin-bottom: 1rem;
}}
.score-hero {{
    display: flex;
    align-items: center;
    gap: 2rem;
    margin: 1.5rem 0;
    padding: 1.5rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
}}
.score-ring {{
    position: relative;
    width: 120px;
    height: 120px;
    flex-shrink: 0;
}}
.score-ring svg {{ display: block; transform: rotate(-90deg); }}
.score-scale {{
    font-size: 12px;
    color: var(--text-secondary, #595959);
    margin-top: 6px;
}}
.score-ring .score-value {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-family: var(--serif);
    font-size: 2rem;
    font-weight: 700;
}}
.score-meta .score-label {{
    font-family: var(--serif);
    font-size: 1.3rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
    color: var(--ink);
}}
.score-meta .score-desc {{
    color: var(--text-muted);
    font-size: 0.9rem;
}}
.sheet-score {{
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: var(--radius);
    font-size: 0.8rem;
    font-weight: 600;
    margin-left: 0.5rem;
}}
.controls {{
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
    margin: 1rem 0 1.5rem;
    padding: 1rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
}}
.filter-btn {{
    padding: 0.4rem 0.8rem;
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    background: transparent;
    color: var(--text);
    cursor: pointer;
    font-family: var(--sans);
    font-size: 0.85rem;
    font-weight: 600;
    transition: all 0.1s ease-out;
}}
.filter-btn:hover {{ border-color: var(--chicago); color: var(--chicago); }}
.filter-btn.active {{ background: var(--chicago); color: #fff; border-color: var(--chicago); }}
.filter-btn.active-high {{ background: var(--high); border-color: var(--high); color: #fff; }}
.filter-btn.active-medium {{ background: var(--medium); border-color: var(--medium); color: #fff; }}
.filter-btn.active-low {{ background: var(--low); border-color: var(--low); color: #fff; }}
.search-box {{
    padding: 8px 12px;
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    background: #ffffff;
    color: var(--text);
    font-family: var(--sans);
    font-size: 0.85rem;
    flex: 1;
    min-width: 200px;
    height: 40px;
}}
.search-box:focus {{ border: 2px solid var(--chicago); outline: none; }}
.search-box::placeholder {{ color: #b3b3b3; }}
.toc {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1rem 1.5rem;
    margin: 1rem 0;
}}
.toc-title {{
    font-family: var(--serif);
    font-weight: 700;
    margin-bottom: 0.5rem;
    color: var(--ink);
}}
.toc a {{
    color: var(--text); text-decoration: underline;
    font-size: 0.9rem;
}}
.toc a:hover {{ color: var(--chicago); }}
.toc ul {{ list-style: none; padding: 0; margin: 0; }}
.toc li {{ padding: 0.25rem 0; }}
.sheet-section {{ }}
.sheet-toggle {{
    cursor: pointer;
    user-select: none;
}}
.sheet-toggle::before {{
    content: '▼ ';
    font-size: 0.7em;
    transition: transform 0.2s ease-in-out;
    display: inline-block;
}}
.sheet-toggle.collapsed::before {{ content: '▶ '; }}
.sheet-body.hidden {{ display: none; }}
.field-card.hidden {{ display: none; }}
.fix-block {{
    margin-top: 0.5rem;
    background: #f2f2f2;
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    overflow: hidden;
}}
.fix-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.4rem 0.8rem;
    background: var(--chicago-95);
    font-size: 0.8rem;
    color: var(--chicago);
    font-weight: 600;
}}
.fix-copy {{
    cursor: pointer;
    background: none;
    border: 1px solid var(--chicago);
    color: var(--chicago);
    border-radius: var(--radius);
    padding: 0.15rem 0.5rem;
    font-size: 0.75rem;
    font-family: var(--sans);
    font-weight: 600;
}}
.fix-copy:hover {{ background: var(--chicago); color: #fff; }}
.fix-code {{
    padding: 0.6rem 0.8rem;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.8rem;
    color: var(--ink);
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.4;
}}
.fix-desc {{
    font-size: 0.8rem;
    color: var(--text-muted);
    padding: 0.3rem 0.8rem 0;
    font-style: italic;
}}
.trend-banner {{
    display: flex;
    gap: 1.5rem;
    align-items: center;
    padding: 1rem 1.5rem;
    background: var(--chicago-95);
    border: 1px solid var(--chicago-85);
    border-radius: var(--radius);
    margin: 1rem 0;
    font-size: 0.9rem;
}}
.trend-banner .delta {{
    font-family: var(--serif);
    font-size: 1.3rem;
    font-weight: 700;
}}
.delta.positive {{ color: var(--low); }}
.delta.negative {{ color: var(--high); }}
.delta.neutral {{ color: var(--text-muted); }}
.schema-violation {{
    border-left: 3px solid var(--accent);
    padding: 0.75rem 1rem;
    margin: 0.75rem 0;
    background: var(--red-95);
    border-radius: 0 var(--radius) var(--radius) 0;
}}
.footer {{
    margin-top: 60px;
    padding-top: 1rem;
    border-top: 1px solid var(--card-border);
    color: var(--text-muted);
    font-size: 0.85rem;
    text-align: center;
}}
@media print {{
    body {{ background-color: #ffffff; }}
}}
@media (max-width: 640px) {{
    body {{ padding: 32px 16px; }}
    h1 {{ font-size: 1.4rem; }}
    .score-hero {{ flex-direction: column; text-align: center; }}
    .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .controls {{ flex-direction: column; }}
}}
</style>
</head>
<body>

<h1>Data Hygiene Audit Report</h1>
<p class="subtitle">{_h(results['input_file'])} &mdash; {results['audit_timestamp']}</p>
""")

    overall = results.get('overall_score', 100)
    label = score_label(overall)
    _band = score_band(overall)
    score_color = _OVERALL_COLORS[_band]
    score_desc = _OVERALL_DESC[_band]

    pct = min(overall, 100)
    circumference = 2 * 3.14159 * 52
    dash = circumference * pct / 100
    gap = circumference - dash

    parts.append(f"""
<div class="score-hero">
    <div class="score-ring">
        <svg width="120" height="120" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52"
                fill="none" stroke="var(--card-border)" stroke-width="8"/>
            <circle cx="60" cy="60" r="52"
                fill="none" stroke="{score_color}" stroke-width="8"
                stroke-dasharray="{dash:.1f} {gap:.1f}"
                stroke-linecap="round"/>
        </svg>
        <div class="score-value" style="color:{score_color}">{overall}</div>
    </div>
    <div class="score-meta">
        <div class="score-label">{label}</div>
        <div class="score-desc">{score_desc}</div>
        {_SCORE_SCALE_HTML}
    </div>
</div>

""")

    trend = results.get('trend')
    if trend:
        delta = trend['overall_score_delta']
        if delta > 0:
            delta_cls = 'positive'
            arrow = f'↑{delta}'
        elif delta < 0:
            delta_cls = 'negative'
            arrow = f'↓{abs(delta)}'
        else:
            delta_cls = 'neutral'
            arrow = '='
        td = trend['total_issues_delta']
        td_str = f"+{td}" if td > 0 else str(td)
        parts.append(f"""
<div class="trend-banner">
    <div>
        <span class="delta {delta_cls}">{arrow}</span>
        <span> vs baseline ({_h(trend['baseline_timestamp'])})</span>
    </div>
    <div>Score: {trend['overall_score_previous']} → {overall}</div>
    <div>Issues: {trend['total_issues_previous']} → {total_issues} ({td_str})</div>
</div>
""")

    parts.append(f"""
<div class="summary-grid">
    <div class="summary-card info">
        <div class="number">{total_issues}</div>
        <div class="label">Total Issues</div></div>
    <div class="summary-card high">
        <div class="number">{severity_totals.get('High', 0)}</div>
        <div class="label">High Severity</div></div>
    <div class="summary-card medium">
        <div class="number">{severity_totals.get('Medium', 0)}</div>
        <div class="label">Medium Severity</div></div>
    <div class="summary-card low">
        <div class="number">{severity_totals.get('Low', 0)}</div>
        <div class="label">Low Severity</div></div>
</div>

<div class="controls">
    <button class="filter-btn active" data-severity="all" onclick="filterSeverity('all')">All</button>
    <button class="filter-btn" data-severity="High" onclick="filterSeverity('High')">High</button>
    <button class="filter-btn" data-severity="Medium" onclick="filterSeverity('Medium')">Medium</button>
    <button class="filter-btn" data-severity="Low" onclick="filterSeverity('Low')">Low</button>
    <input class="search-box" type="text" placeholder="Search by column name or issue..."
        oninput="searchFields(this.value)">
</div>

<div class="toc">
    <div class="toc-title">Table of Contents</div>
    <ul>
""")

    for sheet_name, sheet_data in results['sheets'].items():
        sid = _h(sheet_name.replace(' ', '-').lower())
        ss = sheet_data.get('health_score', 100)
        parts.append(
            f'        <li><a href="#sheet-{sid}">'
            f'{_h(sheet_name)} ({ss}/100)</a></li>\n'
        )
    parts.append("    </ul>\n</div>\n")

    for sheet_name, sheet_data in results['sheets'].items():
        ss = sheet_data.get('health_score', 100)
        ss_color = _SHEET_COLORS[score_band(ss)]
        sid = _h(sheet_name.replace(' ', '-').lower())
        parts.append(f"""
<div class="sheet-section" id="sheet-{sid}">
<h2 class="sheet-toggle" onclick="toggleSheet(this)">Sheet: {_h(sheet_name)}
    <span class="sheet-score" style="background:{ss_color};\
color:#fff">{ss}/100</span></h2>
<div class="sheet-body">
<p style="color:var(--text-muted);margin-bottom:1rem;">
{sheet_data['row_count']} rows &times; {sheet_data['col_count']} columns</p>
""")
        for col_name, field_data in sheet_data['fields'].items():
            null = field_data['null_analysis']
            issues = field_data['issues']
            ftype = field_data['inferred_type']

            if null['missing_pct'] < 10:
                null_color = 'var(--low)'
            elif null['missing_pct'] < 30:
                null_color = 'var(--medium)'
            else:
                null_color = 'var(--high)'

            # Sort to a fixed High>Medium>Low order before emitting: a bare
            # set iterates in hash order, so the same input produced different
            # `data-severities` bytes run-to-run (DECISIONS 2026-08-07). The
            # secondary key keeps any unexpected value deterministic too.
            _sev_rank = {'High': 0, 'Medium': 1, 'Low': 2}
            severities = ' '.join(sorted(
                set(i['severity'] for i in issues),
                key=lambda s: (_sev_rank.get(s, 99), s)))
            parts.append(f"""
<div class="field-card" data-field="{_h(col_name.lower())}" data-severities="{severities}">
    <div class="field-header">
        <span class="field-name">{_h(col_name)}</span>
        <span class="field-type">{_h(ftype)}</span>
    </div>
    <div style="font-size:0.85rem;color:var(--text-muted);">
        Missing: {null['total_missing']} / {null['total_rows']} ({null['missing_pct']}%)
        {f" &mdash; {null['whitespace_only']} whitespace-only" if null['whitespace_only'] else ""}
    </div>
    <div class="null-bar"><div class="null-bar-fill"
        style="width:{min(null['missing_pct'], 100)}%;background:{null_color};"></div></div>
""")
            profile = field_data.get('profile', {})
            if profile:
                stats_parts = [
                    f"{profile['cardinality']} distinct",
                    f"{profile['uniqueness_pct']}% unique",
                    f"avg len {profile['avg_length']}",
                ]
                if 'min_value' in profile:
                    stats_parts.append(
                        f"range {profile['min_value']}"
                        f"–{profile['max_value']}"
                    )
                parts.append(
                    '<div style="font-size:0.8rem;color:var(--text-muted);'
                    'margin:0.2rem 0 0.4rem 0;">'
                    f'{" &nbsp;|&nbsp; ".join(stats_parts)}</div>'
                )

            for issue in issues:
                sev = issue['severity']
                itype = issue['type']
                detail = issue['detail']
                why = issue.get('why', '')

                parts.append(f'<div class="issue severity-{sev}">')
                parts.append(
                    f'<span class="severity-badge {sev}">{sev}</span> '
                )

                # Shared one-line headline (bold label + detail); type-specific
                # rich extras (tables, sample lists) are appended below.
                label, detail_text = issue_headline(itype, detail, issue)
                parts.append(f'<strong>{_h(label)}</strong>')
                if detail_text:
                    parts.append(f' &mdash; {_h(detail_text)}')

                if itype == 'mixed_format':
                    parts.append(
                        '<table class="format-table">'
                        '<tr><th>Format</th><th>Count</th></tr>'
                    )
                    for fmt, cnt in detail['format_distribution'].items():
                        parts.append(
                            f'<tr><td>{_h(fmt)}</td>'
                            f'<td>{cnt}</td></tr>'
                        )
                    parts.append('</table>')
                    if detail.get('sample_nonstandard'):
                        samples = ", ".join(
                            _h(s)
                            for s in detail["sample_nonstandard"][:3]
                        )
                        parts.append(
                            '<div style="font-size:0.85rem;'
                            'color:var(--text-muted);">'
                            f'Non-standard samples: {samples}</div>'
                        )

                elif itype == 'wrong_purpose':
                    if detail.get('row') is not None:
                        parts.append(f' (row {detail["row"] + 2})')

                elif itype == 'custom_rule':
                    examples = detail.get('examples', [])
                    if examples:
                        sample_str = ', '.join(
                            f'"{_h(str(e))}"' for e in examples[:3]
                        )
                        parts.append(
                            '<div style="font-size:0.85rem;'
                            'color:var(--text-muted);">'
                            f'Examples: {sample_str}</div>'
                        )

                elif itype not in KNOWN_ISSUE_TYPES:
                    parts.append(
                        f': {_h(json.dumps(detail, default=str))}'
                    )

                if why:
                    parts.append(
                        '<div class="why-box">'
                        '<strong>Why this matters:</strong>'
                        f' {_h(why)}</div>'
                    )
                fix = issue.get('fix')
                if fix:
                    parts.append(_render_fix(fix))
                parts.append('</div>')

            parts.append('</div>')

        if sheet_data['phantom_duplicates']:
            parts.append('<h3>Phantom &amp; Exact Duplicates</h3>')
            for dup in sheet_data['phantom_duplicates']:
                sev = dup['severity']
                dtype = (
                    'Exact Duplicate'
                    if dup['type'] == 'exact_duplicate'
                    else 'Phantom Duplicate'
                )
                parts.append(f"""
<div class="dup-group">
    <span class="severity-badge {sev}">{sev}</span>
    <strong>{dtype}</strong> &mdash; {dup['group_size']} rows:\
 {', '.join(str(r) for r in dup['rows'])}
    <table class="format-table">
        <tr>{''.join(f'<th>{_h(k)}</th>' for k in dup['sample_data'][0].keys())}</tr>
""")
                for row in dup['sample_data']:
                    parts.append(
                        '<tr>'
                        + ''.join(
                            f'<td>{_h(v)}</td>' for v in row.values()
                        )
                        + '</tr>'
                    )
                parts.append('</table>')
                parts.append(
                    '<div class="why-box">'
                    '<strong>Why this matters:</strong>'
                    f' {_h(dup["why"])}</div>'
                )
                dup_fix = dup.get('fix')
                if dup_fix:
                    parts.append(_render_fix(dup_fix))
                parts.append('</div>')

        if sheet_data.get('fuzzy_duplicates'):
            parts.append('<h3>Fuzzy Duplicates</h3>')
            for fuzz in sheet_data['fuzzy_duplicates']:
                sev = fuzz['severity']
                method = fuzz['match_method'].title()
                parts.append(f"""
<div class="dup-group">
    <span class="severity-badge {sev}">{sev}</span>
    <strong>Fuzzy Match ({method})</strong> &mdash;\
 {fuzz['group_size']} rows:\
 {', '.join(str(r) for r in fuzz['rows'])}""")
                if fuzz.get('sample_data'):
                    parts.append(
                        '<table class="format-table"><tr>'
                        + ''.join(
                            f'<th>{_h(k)}</th>'
                            for k in fuzz['sample_data'][0].keys()
                        )
                        + '</tr>'
                    )
                    for row in fuzz['sample_data']:
                        parts.append(
                            '<tr>'
                            + ''.join(
                                f'<td>{_h(v)}</td>'
                                for v in row.values()
                            )
                            + '</tr>'
                        )
                    parts.append('</table>')
                diffs = fuzz.get('field_differences', {})
                if diffs:
                    parts.append(
                        '<div style="font-size:0.85rem;'
                        'margin-top:0.3rem;">'
                        '<strong>Differences:</strong><ul'
                        ' style="margin:0.2rem 0;">'
                    )
                    for col, diff in diffs.items():
                        if isinstance(diff, dict):
                            vals = ', '.join(
                                f'"{_h(v)}"'
                                for v in diff.get('values', [])
                            )
                            sim = diff.get('similarity')
                            sim_str = (
                                f' (similarity: {sim})'
                                if sim is not None else ''
                            )
                            parts.append(
                                f'<li>{_h(col)}: {vals}'
                                f'{sim_str}</li>'
                            )
                        else:
                            vals = ', '.join(
                                f'"{_h(v)}"' for v in diff
                            )
                            parts.append(
                                f'<li>{_h(col)}: {vals}</li>'
                            )
                    parts.append('</ul></div>')
                parts.append(
                    '<div class="why-box">'
                    '<strong>Why this matters:</strong>'
                    f' {_h(fuzz["why"])}</div>'
                )
                fuzz_fix = fuzz.get('fix')
                if fuzz_fix:
                    parts.append(_render_fix(fuzz_fix))
                parts.append('</div>')

        if sheet_data.get('schema_violations'):
            parts.append('<h3>Schema Violations</h3>')
            for sv in sheet_data['schema_violations']:
                sev = sv['severity']
                svtype = sv['type']
                detail = sv.get('detail', {})
                if svtype == 'schema_type_mismatch':
                    desc = (
                        f"Column <strong>{_h(detail.get('column', ''))}</strong>:"
                        f" expected <em>{_h(detail.get('expected_type', ''))}</em>,"
                        f" got <em>{_h(detail.get('actual_type', ''))}</em>"
                    )
                elif svtype == 'schema_missing_column':
                    desc = (
                        f"Required column <strong>"
                        f"{_h(detail.get('expected_column', ''))}</strong> is missing"
                    )
                elif svtype == 'schema_completeness_violation':
                    desc = (
                        f"Column <strong>{_h(detail.get('column', ''))}</strong>:"
                        f" {detail.get('actual_missing_pct', 0)}% missing"
                        f" (max {detail.get('max_missing_pct', 0)}%)"
                    )
                else:
                    desc = _h(svtype)
                parts.append(
                    f'<div class="schema-violation">'
                    f'<span class="severity-badge {sev}">{sev}</span> '
                    f'{desc}'
                )
                why = sv.get('why', '')
                if why:
                    parts.append(
                        '<div class="why-box">'
                        '<strong>Why this matters:</strong>'
                        f' {_h(why)}</div>'
                    )
                parts.append('</div>')

        parts.append('</div></div>')  # close sheet-body, sheet-section

    parts.append(f"""
<div class="footer">
    Data Hygiene Audit &mdash; Generated {results['audit_timestamp']}\
 &mdash; Lailara LLC
</div>

<script>
function filterSeverity(sev) {{
    document.querySelectorAll('.filter-btn').forEach(b => {{
        b.className = 'filter-btn';
        if (b.dataset.severity === sev) {{
            b.classList.add(sev === 'all' ? 'active' : 'active-' + sev.toLowerCase());
        }}
    }});
    document.querySelectorAll('.field-card').forEach(card => {{
        if (sev === 'all') {{
            card.classList.remove('hidden');
        }} else {{
            const sevs = card.dataset.severities || '';
            card.classList.toggle('hidden', !sevs.includes(sev));
        }}
    }});
}}

function searchFields(query) {{
    const q = query.toLowerCase();
    document.querySelectorAll('.field-card').forEach(card => {{
        const field = card.dataset.field || '';
        const text = card.textContent.toLowerCase();
        card.classList.toggle('hidden', q && !field.includes(q) && !text.includes(q));
    }});
    document.querySelectorAll('.filter-btn').forEach(b => {{
        b.className = 'filter-btn';
        if (b.dataset.severity === 'all') b.classList.add('active');
    }});
}}

function toggleSheet(el) {{
    el.classList.toggle('collapsed');
    const body = el.nextElementSibling;
    if (body) body.classList.toggle('hidden');
}}

function copyFix(btn) {{
    const block = btn.closest('.fix-block');
    const code = block.querySelector('.fix-code').textContent;
    navigator.clipboard.writeText(code).then(() => {{
        btn.textContent = 'Copied!';
        setTimeout(() => {{ btn.textContent = 'Copy'; }}, 2000);
    }});
}}
</script>
</body></html>""")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))
    return output_path
