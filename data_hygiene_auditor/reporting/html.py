"""HTML report generator."""

import json
from collections import Counter
from html import escape as _html_escape


def _h(val):
    """Escape a value for safe inclusion in HTML text or attributes."""
    return _html_escape(str(val), quote=True)


def generate_html(results, output_path):
    """Generate a client-readable HTML report."""
    total_issues = 0
    severity_totals = Counter()
    for sheet in results['sheets'].values():
        for field in sheet['fields'].values():
            for issue in field['issues']:
                total_issues += 1
                severity_totals[issue['severity']] += 1
        for d in sheet['phantom_duplicates']:
            total_issues += 1
            severity_totals[d['severity']] += 1
        for f in sheet.get('fuzzy_duplicates', []):
            total_issues += 1
            severity_totals[f['severity']] += 1

    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Data Hygiene Audit — {_h(results['input_file'])}</title>
<style>
:root {{
    --bg: #1a1a2e;
    --card: #16213e;
    --card-border: #0f3460;
    --text: #e0e0e0;
    --text-muted: #8892a0;
    --accent: #e94560;
    --accent-warm: #d4a574;
    --high: #DC3545;
    --medium: #FFC107;
    --low: #28A745;
    --info: #4a90d9;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
}}
h1 {{ color: var(--accent); font-size: 1.8rem; margin-bottom: 0.25rem; }}
h2 {{
    color: var(--accent-warm); font-size: 1.4rem; margin: 2rem 0 1rem;
    border-bottom: 1px solid var(--card-border); padding-bottom: 0.5rem;
}}
h3 {{ color: var(--text); font-size: 1.1rem; margin: 1.5rem 0 0.5rem; }}
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
    border-radius: 8px;
    padding: 1.2rem;
    text-align: center;
}}
.summary-card .number {{ font-size: 2rem; font-weight: 700; }}
.summary-card .label {{
    color: var(--text-muted); font-size: 0.85rem;
    text-transform: uppercase; letter-spacing: 0.05em;
}}
.high .number {{ color: var(--high); }}
.medium .number {{ color: var(--medium); }}
.low .number {{ color: var(--low); }}
.info .number {{ color: var(--info); }}
.field-card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 8px;
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
    background: var(--card-border);
    color: var(--text-muted);
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.8rem;
}}
.null-bar {{
    height: 6px;
    background: #2a2a4a;
    border-radius: 3px;
    margin: 0.5rem 0;
    overflow: hidden;
}}
.null-bar-fill {{
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s;
}}
.issue {{
    border-left: 3px solid var(--text-muted);
    padding: 0.75rem 1rem;
    margin: 0.75rem 0;
    background: rgba(255,255,255,0.02);
    border-radius: 0 6px 6px 0;
}}
.issue.severity-High {{ border-left-color: var(--high); }}
.issue.severity-Medium {{ border-left-color: var(--medium); }}
.issue.severity-Low {{ border-left-color: var(--low); }}
.severity-badge {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 10px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.severity-badge.High {{ background: var(--high); color: #fff; }}
.severity-badge.Medium {{ background: var(--medium); color: #000; }}
.severity-badge.Low {{ background: var(--low); color: #fff; }}
.why-box {{
    margin-top: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: rgba(74, 144, 217, 0.08);
    border-radius: 4px;
    font-size: 0.9rem;
    color: var(--text-muted);
}}
.why-box strong {{ color: var(--info); }}
.format-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0;
    font-size: 0.9rem;
}}
.format-table th, .format-table td {{
    text-align: left;
    padding: 0.4rem 0.75rem;
    border-bottom: 1px solid var(--card-border);
}}
.format-table th {{ color: var(--text-muted); font-weight: 600; }}
.dup-group {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 8px;
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
    border-radius: 12px;
}}
.score-ring {{
    position: relative;
    width: 120px;
    height: 120px;
    flex-shrink: 0;
}}
.score-ring svg {{ transform: rotate(-90deg); }}
.score-ring .score-value {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 2rem;
    font-weight: 700;
}}
.score-meta .score-label {{
    font-size: 1.3rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}}
.score-meta .score-desc {{
    color: var(--text-muted);
    font-size: 0.9rem;
}}
.sheet-score {{
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 10px;
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
    border-radius: 8px;
}}
.filter-btn {{
    padding: 0.4rem 0.8rem;
    border: 1px solid var(--card-border);
    border-radius: 6px;
    background: transparent;
    color: var(--text);
    cursor: pointer;
    font-size: 0.85rem;
    transition: all 0.2s;
}}
.filter-btn:hover {{ border-color: var(--accent); }}
.filter-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.filter-btn.active-high {{ background: var(--high); border-color: var(--high); color: #fff; }}
.filter-btn.active-medium {{ background: var(--medium); border-color: var(--medium); color: #000; }}
.filter-btn.active-low {{ background: var(--low); border-color: var(--low); color: #fff; }}
.search-box {{
    padding: 0.4rem 0.8rem;
    border: 1px solid var(--card-border);
    border-radius: 6px;
    background: var(--bg);
    color: var(--text);
    font-size: 0.85rem;
    flex: 1;
    min-width: 200px;
}}
.search-box::placeholder {{ color: var(--text-muted); }}
.toc {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 1rem 1.5rem;
    margin: 1rem 0;
}}
.toc-title {{ font-weight: 600; margin-bottom: 0.5rem; }}
.toc a {{
    color: var(--accent); text-decoration: none;
    font-size: 0.9rem;
}}
.toc a:hover {{ text-decoration: underline; }}
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
    transition: transform 0.2s;
    display: inline-block;
}}
.sheet-toggle.collapsed::before {{ content: '▶ '; }}
.sheet-body.hidden {{ display: none; }}
.field-card.hidden {{ display: none; }}
.footer {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--card-border);
    color: var(--text-muted);
    font-size: 0.85rem;
    text-align: center;
}}
@media (max-width: 600px) {{
    body {{ padding: 1rem; }}
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
    if overall >= 90:
        score_color = 'var(--low)'
        score_label = 'Clean'
        score_desc = 'This dataset is in good shape.'
    elif overall >= 70:
        score_color = 'var(--medium)'
        score_label = 'Needs Attention'
        score_desc = 'Several issues should be addressed before use.'
    else:
        score_color = 'var(--high)'
        score_label = 'Significant Issues'
        score_desc = 'This dataset has serious quality problems.'

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
        <div class="score-label">{score_label}</div>
        <div class="score-desc">{score_desc}</div>
    </div>
</div>

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
        if ss >= 90:
            ss_color = 'var(--low)'
        elif ss >= 70:
            ss_color = 'var(--medium)'
        else:
            ss_color = 'var(--high)'
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

            severities = ' '.join(set(i['severity'] for i in issues))
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
            for issue in issues:
                sev = issue['severity']
                itype = issue['type']
                detail = issue['detail']
                why = issue.get('why', '')

                parts.append(f'<div class="issue severity-{sev}">')
                parts.append(
                    f'<span class="severity-badge {sev}">{sev}</span> '
                )

                if itype == 'mixed_format':
                    total = (
                        detail["dominant_count"]
                        + detail["inconsistent_count"]
                    )
                    parts.append(
                        f'<strong>Mixed {_h(detail["field_type"])}'
                        f' formats</strong>'
                        f' &mdash; {detail["inconsistent_count"]}'
                        f' of {total}'
                        f' values deviate from dominant format'
                        f' ({_h(detail["dominant_format"])})'
                    )
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
                    parts.append(
                        f'<strong>{_h(detail["issue"])}</strong>'
                    )
                    if detail.get('example'):
                        parts.append(
                            f' &mdash; e.g. "{_h(detail["example"])}"'
                        )
                    if detail.get('row') is not None:
                        parts.append(f' (row {detail["row"] + 2})')

                elif itype in ('placeholder_value', 'placeholder'):
                    parts.append(
                        f'<strong>Placeholder detected:</strong>'
                        f' "{_h(detail["value"])}" appears'
                        f' {detail["count"]} times ({detail["pct"]}%)'
                    )

                elif itype == 'suspicious_repetition':
                    parts.append(
                        f'<strong>Suspicious repetition:</strong>'
                        f' "{_h(detail["value"])}" appears'
                        f' {detail["count"]} times ({detail["pct"]}%)'
                    )

                elif itype == 'null_analysis':
                    parts.append(
                        f'<strong>High missing rate:</strong>'
                        f' {detail["total_missing"]} of'
                        f' {detail["total_rows"]} values missing'
                        f' ({detail["missing_pct"]}%)'
                    )

                else:
                    parts.append(
                        f'<strong>{_h(itype)}</strong>:'
                        f' {_h(json.dumps(detail, default=str))}'
                    )

                if why:
                    parts.append(
                        '<div class="why-box">'
                        '<strong>Why this matters:</strong>'
                        f' {_h(why)}</div>'
                    )
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
</script>
</body></html>""")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))
    return output_path
