"""PDF report generator."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors as rl_colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..core import count_issues, issue_headline, score_label
from . import palette as P
from .brand_fonts import SANS, SANS_BOLD, SERIF_BOLD, register_fonts


def _p(val: object) -> str:
    """Escape a value for inclusion inside a reportlab Paragraph."""
    return _xml_escape(str(val))


def generate_pdf(results: dict[str, Any], output_path: str) -> str:
    """Generate a clean PDF report matching the HTML content."""
    register_fonts()
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )
    styles = getSampleStyleSheet()
    # Sample styles used directly default to Helvetica/Times internally;
    # pin them to the brand faces so nothing inherits a base-14 font.
    styles['Title'].fontName = SERIF_BOLD
    styles['Normal'].fontName = SANS
    styles.add(ParagraphStyle(
        name='SectionHead', parent=styles['Heading2'],
        fontName=SERIF_BOLD,
        textColor=rl_colors.HexColor(P.INK), fontSize=14,
        spaceAfter=8, spaceBefore=16,
    ))
    styles.add(ParagraphStyle(
        name='FieldHead', parent=styles['Heading3'],
        fontName=SERIF_BOLD,
        fontSize=11, spaceAfter=4, spaceBefore=10,
        textColor=rl_colors.HexColor(P.LONDON_20),
    ))
    styles.add(ParagraphStyle(
        name='SmallBody', parent=styles['Normal'],
        fontName=SANS,
        fontSize=9, leading=12, spaceAfter=4,
        textColor=rl_colors.HexColor(P.LONDON_20),
    ))
    styles.add(ParagraphStyle(
        name='WhyBox', parent=styles['Normal'],
        fontName=SANS,
        fontSize=8.5, leading=11, leftIndent=12,
        textColor=rl_colors.HexColor(P.LONDON_35),
        spaceAfter=6, spaceBefore=2,
    ))
    styles.add(ParagraphStyle(
        name='SevHigh', parent=styles['Normal'],
        fontSize=9, textColor=rl_colors.HexColor(P.SEV_HIGH),
        fontName=SANS_BOLD,
    ))
    styles.add(ParagraphStyle(
        name='SevMedium', parent=styles['Normal'],
        fontSize=9, textColor=rl_colors.HexColor(P.SEV_MEDIUM),
        fontName=SANS_BOLD,
    ))
    styles.add(ParagraphStyle(
        name='SevLow', parent=styles['Normal'],
        fontSize=9, textColor=rl_colors.HexColor(P.SEV_LOW),
        fontName=SANS_BOLD,
    ))

    story = []

    story.append(Paragraph(
        "Data Hygiene Audit Report", styles['Title'],
    ))
    story.append(Paragraph(
        f"{_p(results['input_file'])} — {results['audit_timestamp']}",
        styles['Normal'],
    ))
    overall = results.get('overall_score', 100)
    story.append(Paragraph(
        f"<b>Health Score: {overall}/100</b>"
        f" — {score_label(overall)}",
        ParagraphStyle(
            name='ScoreHead', parent=styles['Heading2'],
            fontName=SERIF_BOLD,
            fontSize=16, spaceAfter=12,
        ),
    ))
    story.append(Spacer(1, 8))

    counts = count_issues(results)

    summary_data = [
        ['Total Issues', 'High', 'Medium', 'Low'],
        [
            str(counts.get('total', 0)),
            str(counts.get('High', 0)),
            str(counts.get('Medium', 0)),
            str(counts.get('Low', 0)),
        ],
    ]
    t = Table(summary_data, colWidths=[1.5*inch]*4)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor(P.CHICAGO_20)),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTNAME', (0, 0), (-1, -1), SANS),
        ('FONTNAME', (0, 0), (-1, 0), SANS_BOLD),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.HexColor(P.LONDON_85)),
        ('BACKGROUND', (1, 1), (1, 1), rl_colors.HexColor(P.SEV_HIGH_BG)),
        ('BACKGROUND', (2, 1), (2, 1), rl_colors.HexColor(P.SEV_MEDIUM_BG)),
        ('BACKGROUND', (3, 1), (3, 1), rl_colors.HexColor(P.SEV_LOW_BG)),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    trend = results.get('trend')
    if trend:
        delta = trend['overall_score_delta']
        sign = '+' if delta > 0 else ''
        td = trend['total_issues_delta']
        td_sign = '+' if td > 0 else ''
        story.append(Paragraph(
            f"<b>Trend vs Baseline</b> ({_p(trend['baseline_timestamp'])})",
            styles['FieldHead'],
        ))
        story.append(Paragraph(
            f"Score: {trend['overall_score_previous']} → "
            f"{results.get('overall_score', 0)} ({sign}{delta})  |  "
            f"Issues: {trend['total_issues_previous']} → "
            f"{counts.get('total', 0)} ({td_sign}{td})",
            styles['SmallBody'],
        ))
        story.append(Spacer(1, 8))

    for sheet_name, sheet_data in results['sheets'].items():
        story.append(Paragraph(
            f"Sheet: {_p(sheet_name)}", styles['SectionHead'],
        ))
        story.append(Paragraph(
            f"{sheet_data['row_count']} rows"
            f" × {sheet_data['col_count']} columns",
            styles['SmallBody'],
        ))

        for col_name, field_data in sheet_data['fields'].items():
            issues = field_data['issues']
            if not issues:
                continue

            null = field_data['null_analysis']
            ftype = field_data['inferred_type']

            story.append(Paragraph(
                f"<b>{_p(col_name)}</b> <i>({_p(ftype)})</i>"
                f" — Missing: {null['total_missing']}"
                f"/{null['total_rows']}"
                f" ({null['missing_pct']}%)",
                styles['FieldHead'],
            ))

            profile = field_data.get('profile', {})
            if profile:
                stats = (
                    f"{profile['cardinality']} distinct"
                    f" | {profile['uniqueness_pct']}% unique"
                    f" | avg len {profile['avg_length']}"
                )
                if 'min_value' in profile:
                    stats += (
                        f" | range {profile['min_value']}"
                        f"–{profile['max_value']}"
                    )
                story.append(Paragraph(stats, styles['SmallBody']))

            for issue in issues:
                sev = issue['severity']
                detail = issue['detail']
                itype = issue['type']
                sev_style = f'Sev{sev}'

                # Shared one-line headline; the mixed-format table and
                # custom-rule example list are PDF-specific extras below.
                label, detail_text = issue_headline(itype, detail, issue)
                text = f"[{sev}] {_p(label)}"
                if detail_text:
                    text += f" — {_p(detail_text)}"
                story.append(Paragraph(
                    text,
                    styles.get(sev_style, styles['SmallBody']),
                ))

                if itype == 'mixed_format':
                    fmt_data = [['Format', 'Count']]
                    for fmt, cnt in (
                        detail['format_distribution'].items()
                    ):
                        fmt_data.append([fmt, str(cnt)])
                    ft = Table(fmt_data, colWidths=[3*inch, 1*inch])
                    ft.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), SANS),
                        ('FONTNAME', (0, 0), (-1, 0), SANS_BOLD),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (0, 0), (-1, 0),
                         rl_colors.HexColor(P.CHICAGO_20)),
                        ('TEXTCOLOR', (0, 0), (-1, 0),
                         rl_colors.white),
                        ('GRID', (0, 0), (-1, -1), 0.25,
                         rl_colors.HexColor(P.LONDON_85)),
                    ]))
                    story.append(ft)

                elif itype == 'custom_rule':
                    examples = detail.get('examples', [])
                    if examples:
                        sample_str = ', '.join(
                            f'"{_p(str(e))}"' for e in examples[:3]
                        )
                        story.append(Paragraph(
                            f"Examples: {sample_str}",
                            styles['SmallBody'],
                        ))

                why = issue.get('why', '')
                if why:
                    story.append(Paragraph(
                        f"<b>Why this matters:</b> {_p(why)}",
                        styles['WhyBox'],
                    ))
                fix = issue.get('fix')
                if fix:
                    story.append(Paragraph(
                        f"<b>Suggested fix:</b> {_p(fix['description'])}",
                        styles['WhyBox'],
                    ))
                    story.append(Paragraph(
                        f"<font face='Courier' size='8'>"
                        f"{_p(fix['code'])}</font>",
                        styles['WhyBox'],
                    ))

        if sheet_data['phantom_duplicates']:
            story.append(Paragraph(
                "Phantom &amp; Exact Duplicates",
                styles['FieldHead'],
            ))
            for dup in sheet_data['phantom_duplicates']:
                sev = dup['severity']
                dtype = (
                    'Exact Duplicate'
                    if dup['type'] == 'exact_duplicate'
                    else 'Phantom Duplicate'
                )
                text = (
                    f"[{sev}] {dtype}"
                    f" — {dup['group_size']} rows:"
                    f" {', '.join(str(r) for r in dup['rows'])}"
                )
                story.append(Paragraph(
                    text,
                    styles.get(f'Sev{sev}', styles['SmallBody']),
                ))
                if dup.get('why'):
                    story.append(Paragraph(
                        f"<b>Why this matters:</b> {_p(dup['why'])}",
                        styles['WhyBox'],
                    ))
                dup_fix = dup.get('fix')
                if dup_fix:
                    story.append(Paragraph(
                        f"<b>Suggested fix:</b>"
                        f" {_p(dup_fix['description'])}",
                        styles['WhyBox'],
                    ))

        if sheet_data.get('fuzzy_duplicates'):
            story.append(Paragraph(
                "Fuzzy Duplicates", styles['FieldHead'],
            ))
            for fuzz in sheet_data['fuzzy_duplicates']:
                sev = fuzz['severity']
                method = _p(fuzz['match_method'].title())
                text = (
                    f"[{sev}] Fuzzy Match ({method})"
                    f" — {fuzz['group_size']} rows:"
                    f" {', '.join(str(r) for r in fuzz['rows'])}"
                )
                story.append(Paragraph(
                    text,
                    styles.get(f'Sev{sev}', styles['SmallBody']),
                ))
                diffs = fuzz.get('field_differences', {})
                if diffs:
                    diff_parts = []
                    for col, diff in diffs.items():
                        if isinstance(diff, dict):
                            vals = diff.get('values', [])
                            val_str = ', '.join(
                                f'"{_p(v)}"' for v in vals
                            )
                            diff_parts.append(
                                f"{_p(col)}: {val_str}"
                            )
                        else:
                            val_str = ', '.join(
                                f'"{_p(v)}"' for v in diff
                            )
                            diff_parts.append(
                                f"{_p(col)}: {val_str}"
                            )
                    story.append(Paragraph(
                        "Differences: " + "; ".join(diff_parts),
                        styles['SmallBody'],
                    ))
                if fuzz.get('why'):
                    story.append(Paragraph(
                        f"<b>Why this matters:</b>"
                        f" {_p(fuzz['why'])}",
                        styles['WhyBox'],
                    ))
                fuzz_fix = fuzz.get('fix')
                if fuzz_fix:
                    story.append(Paragraph(
                        f"<b>Suggested fix:</b>"
                        f" {_p(fuzz_fix['description'])}",
                        styles['WhyBox'],
                    ))

        if sheet_data.get('schema_violations'):
            story.append(Paragraph(
                "Schema Violations", styles['FieldHead'],
            ))
            for sv in sheet_data['schema_violations']:
                sev = sv['severity']
                svtype = sv['type']
                detail = sv.get('detail', {})
                if svtype == 'schema_type_mismatch':
                    text = (
                        f"[{sev}] Column '{_p(detail.get('column', ''))}'"
                        f": expected {_p(detail.get('expected_type', ''))}"
                        f", got {_p(detail.get('actual_type', ''))}"
                    )
                elif svtype == 'schema_missing_column':
                    text = (
                        f"[{sev}] Required column"
                        f" '{_p(detail.get('expected_column', ''))}'"
                        f" is missing"
                    )
                elif svtype == 'schema_completeness_violation':
                    text = (
                        f"[{sev}] Column '{_p(detail.get('column', ''))}'"
                        f": {detail.get('actual_missing_pct', 0)}% missing"
                        f" (max {detail.get('max_missing_pct', 0)}%)"
                    )
                else:
                    text = f"[{sev}] {_p(svtype)}"
                story.append(Paragraph(
                    text,
                    styles.get(f'Sev{sev}', styles['SmallBody']),
                ))
                why = sv.get('why', '')
                if why:
                    story.append(Paragraph(
                        f"<b>Why:</b> {_p(why)}",
                        styles['WhyBox'],
                    ))

        story.append(PageBreak())

    story.append(Paragraph(
        f"Data Hygiene Audit — Generated"
        f" {results['audit_timestamp']} — Lailara LLC",
        ParagraphStyle(
            name='Footer', parent=styles['Normal'],
            fontName=SANS,
            fontSize=8, textColor=rl_colors.HexColor(P.LONDON_35),
            alignment=TA_CENTER,
        ),
    ))

    doc.build(story)
    return output_path
