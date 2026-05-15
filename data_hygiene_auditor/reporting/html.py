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
.footer {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--card-border);
    color: var(--text-muted);
    font-size: 0.85rem;
    text-align: center;
}}
</style>
</head>
<body>

<h1>Data Hygiene Audit Report</h1>
<p class="subtitle">{_h(results['input_file'])} &mdash; {results['audit_timestamp']}</p>

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
""")

    for sheet_name, sheet_data in results['sheets'].items():
        parts.append(f"""
<h2>Sheet: {_h(sheet_name)}</h2>
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

            parts.append(f"""
<div class="field-card">
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

    parts.append(f"""
<div class="footer">
    Data Hygiene Audit &mdash; Generated {results['audit_timestamp']}\
 &mdash; Lailara LLC
</div>
</body></html>""")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))
    return output_path
