"""PDF report generator."""

from collections import Counter
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


def _p(val):
    """Escape a value for inclusion inside a reportlab Paragraph."""
    return _xml_escape(str(val))


def generate_pdf(results, output_path):
    """Generate a clean PDF report matching the HTML content."""
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='SectionHead', parent=styles['Heading2'],
        textColor=rl_colors.HexColor('#d4a574'), fontSize=14,
        spaceAfter=8, spaceBefore=16,
    ))
    styles.add(ParagraphStyle(
        name='FieldHead', parent=styles['Heading3'],
        fontSize=11, spaceAfter=4, spaceBefore=10,
    ))
    styles.add(ParagraphStyle(
        name='SmallBody', parent=styles['Normal'],
        fontSize=9, leading=12, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name='WhyBox', parent=styles['Normal'],
        fontSize=8.5, leading=11, leftIndent=12,
        textColor=rl_colors.HexColor('#555555'),
        spaceAfter=6, spaceBefore=2,
    ))
    styles.add(ParagraphStyle(
        name='SevHigh', parent=styles['Normal'],
        fontSize=9, textColor=rl_colors.HexColor('#DC3545'),
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        name='SevMedium', parent=styles['Normal'],
        fontSize=9, textColor=rl_colors.HexColor('#856404'),
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        name='SevLow', parent=styles['Normal'],
        fontSize=9, textColor=rl_colors.HexColor('#155724'),
        fontName='Helvetica-Bold',
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
    if overall >= 90:
        score_label = 'Clean'
    elif overall >= 70:
        score_label = 'Needs Attention'
    else:
        score_label = 'Significant Issues'
    story.append(Paragraph(
        f"<b>Health Score: {overall}/100</b>"
        f" — {score_label}",
        ParagraphStyle(
            name='ScoreHead', parent=styles['Heading2'],
            fontSize=16, spaceAfter=12,
        ),
    ))
    story.append(Spacer(1, 8))

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

    summary_data = [
        ['Total Issues', 'High', 'Medium', 'Low'],
        [
            str(total_issues),
            str(severity_totals.get('High', 0)),
            str(severity_totals.get('Medium', 0)),
            str(severity_totals.get('Low', 0)),
        ],
    ]
    t = Table(summary_data, colWidths=[1.5*inch]*4)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#0f3460')),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.HexColor('#cccccc')),
        ('BACKGROUND', (1, 1), (1, 1), rl_colors.HexColor('#F8D7DA')),
        ('BACKGROUND', (2, 1), (2, 1), rl_colors.HexColor('#FFF3CD')),
        ('BACKGROUND', (3, 1), (3, 1), rl_colors.HexColor('#D4EDDA')),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

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

            for issue in issues:
                sev = issue['severity']
                detail = issue['detail']
                itype = issue['type']
                sev_style = f'Sev{sev}'

                if itype == 'mixed_format':
                    text = (
                        f"[{sev}] Mixed"
                        f" {_p(detail['field_type'])} formats"
                        f" — {detail['inconsistent_count']}"
                        " values deviate"
                        f" from {_p(detail['dominant_format'])}"
                    )
                    story.append(Paragraph(
                        text,
                        styles.get(sev_style, styles['SmallBody']),
                    ))
                    fmt_data = [['Format', 'Count']]
                    for fmt, cnt in (
                        detail['format_distribution'].items()
                    ):
                        fmt_data.append([fmt, str(cnt)])
                    ft = Table(fmt_data, colWidths=[3*inch, 1*inch])
                    ft.setStyle(TableStyle([
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (0, 0), (-1, 0),
                         rl_colors.HexColor('#e8e8e8')),
                        ('GRID', (0, 0), (-1, -1), 0.25,
                         rl_colors.HexColor('#cccccc')),
                    ]))
                    story.append(ft)

                elif itype == 'wrong_purpose':
                    text = f"[{sev}] {_p(detail['issue'])}"
                    if detail.get('example'):
                        text += (
                            f' — e.g. "{_p(detail["example"])}"'
                        )
                    story.append(Paragraph(
                        text,
                        styles.get(sev_style, styles['SmallBody']),
                    ))

                elif itype in ('placeholder_value', 'placeholder'):
                    text = (
                        f'[{sev}] Placeholder:'
                        f' "{_p(detail["value"])}"'
                        f' × {detail["count"]}'
                        f' ({detail["pct"]}%)'
                    )
                    story.append(Paragraph(
                        text,
                        styles.get(sev_style, styles['SmallBody']),
                    ))

                elif itype == 'suspicious_repetition':
                    text = (
                        f'[{sev}] Repetition:'
                        f' "{_p(detail["value"])}"'
                        f' × {detail["count"]}'
                        f' ({detail["pct"]}%)'
                    )
                    story.append(Paragraph(
                        text,
                        styles.get(sev_style, styles['SmallBody']),
                    ))

                elif itype == 'null_analysis':
                    text = (
                        f"[{sev}] High missing rate:"
                        f" {detail['total_missing']}"
                        f"/{detail['total_rows']}"
                        f" ({detail['missing_pct']}%)"
                    )
                    story.append(Paragraph(
                        text,
                        styles.get(sev_style, styles['SmallBody']),
                    ))

                why = issue.get('why', '')
                if why:
                    story.append(Paragraph(
                        f"<b>Why this matters:</b> {_p(why)}",
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

        story.append(PageBreak())

    story.append(Paragraph(
        f"Data Hygiene Audit — Generated"
        f" {results['audit_timestamp']} — Lailara LLC",
        ParagraphStyle(
            name='Footer', parent=styles['Normal'],
            fontSize=8, textColor=rl_colors.HexColor('#999999'),
            alignment=TA_CENTER,
        ),
    ))

    doc.build(story)
    return output_path
