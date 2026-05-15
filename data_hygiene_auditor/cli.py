"""CLI entrypoint for the Data Hygiene Auditor."""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from .core import SUPPORTED_EXTENSIONS, run_audit
from .reporting import generate_excel, generate_html, generate_pdf


def _supports_color():
    """Check if the terminal supports ANSI color codes."""
    if os.environ.get('NO_COLOR'):
        return False
    if sys.platform == 'win32':
        os.system('')
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


_COLOR = _supports_color()


def _c(text, code):
    """Wrap text in ANSI color if supported."""
    if not _COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Data Hygiene Auditor — Detect data quality issues'
            ' in Excel and CSV files'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  data-hygiene-audit --input customers.xlsx --output ./reports
  data-hygiene-audit --input data.csv --output ./reports
  data-hygiene-audit --input data.xlsx --output ./reports --json

Outputs three files:
  - audit_report.html   (visual, client-readable)
  - audit_findings.xlsx (sortable/filterable issue list)
  - audit_report.pdf    (email-ready deliverable)
        """,
    )
    parser.add_argument(
        '--input', '-i', required=True,
        help='Path to input file (.xlsx, .csv, .tsv)',
    )
    parser.add_argument(
        '--output', '-o', required=True,
        help='Output directory for reports',
    )
    parser.add_argument(
        '--json', action='store_true',
        help='Also output raw JSON results',
    )
    parser.add_argument(
        '--threshold', '-t', type=float, default=0.85,
        help='Fuzzy duplicate similarity threshold (0.0-1.0, default: 0.85)',
    )
    parser.add_argument(
        '--schema', '-s',
        help='Path to schema JSON for type/completeness validation',
    )
    parser.add_argument(
        '--generate-schema',
        help='Generate schema from inferred types and save to path',
    )
    parser.add_argument(
        '--baseline', '-b',
        help='Path to previous audit JSON for trend comparison',
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(
            f"Error: Input file not found: {args.input}",
            file=sys.stderr,
        )
        sys.exit(1)

    ext = Path(args.input).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ', '.join(sorted(SUPPORTED_EXTENSIONS))
        print(
            f"Error: Unsupported file type '{ext}'."
            f" Supported: {supported}",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    basename = Path(args.input).stem
    print(f"\n  {_c('Data Hygiene Auditor', '1')}")
    print(f"  Auditing: {_c(args.input, '36')}\n")

    results = run_audit(
        args.input,
        fuzzy_threshold=args.threshold,
        schema_path=args.schema,
        baseline_path=args.baseline,
    )
    sheet_count = len(results['sheets'])
    for i, (name, sdata) in enumerate(results['sheets'].items(), 1):
        score = sdata['health_score']
        score_color = '32' if score >= 90 else ('33' if score >= 70 else '31')
        print(
            f"  [{i}/{sheet_count}] Analyzed sheet: {_c(name, '36')}"
            f"  (score: {_c(str(score), score_color)})"
        )

    html_path = os.path.join(
        args.output, f"{basename}_audit_report.html",
    )
    xlsx_path = os.path.join(
        args.output, f"{basename}_audit_findings.xlsx",
    )
    pdf_path = os.path.join(
        args.output, f"{basename}_audit_report.pdf",
    )

    print("\n  Generating reports...")

    generate_html(results, html_path)
    print(f"    {_c('HTML', '32')}  -> {html_path}")

    generate_excel(results, xlsx_path)
    print(f"    {_c('Excel', '32')} -> {xlsx_path}")

    generate_pdf(results, pdf_path)
    print(f"    {_c('PDF', '32')}   -> {pdf_path}")

    if args.json:
        json_path = os.path.join(
            args.output, f"{basename}_audit_results.json",
        )
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"    {_c('JSON', '32')}  -> {json_path}")

    if args.generate_schema:
        from .schema import generate_schema
        schema_data = generate_schema(results)
        with open(args.generate_schema, 'w') as f:
            json.dump(schema_data, f, indent=2)
        print(f"    {_c('Schema', '32')} -> {args.generate_schema}")

    total_issues = 0
    severity_totals = Counter()
    schema_count = 0
    for sheet in results['sheets'].values():
        for field in sheet['fields'].values():
            for issue in field['issues']:
                total_issues += 1
                severity_totals[issue['severity']] += 1
        for d in sheet['phantom_duplicates']:
            total_issues += 1
            severity_totals[d['severity']] += 1
        for sv in sheet.get('schema_violations', []):
            total_issues += 1
            severity_totals[sv['severity']] += 1
            schema_count += 1

    high = severity_totals.get('High', 0)
    med = severity_totals.get('Medium', 0)
    low = severity_totals.get('Low', 0)

    overall = results['overall_score']
    score_color = '32' if overall >= 90 else ('33' if overall >= 70 else '31')

    score_str = f"{overall}/100"
    trend = results.get('trend')
    if trend:
        delta = trend['overall_score_delta']
        arrow = _c(f'+{delta}', '32') if delta > 0 else _c(f'{delta}', '31') if delta < 0 else '='
        score_str += f" ({arrow} from baseline)"
    print(
        f"\n  Health Score: {_c(score_str, score_color)}"
    )
    issue_line = (
        f"  {_c(str(total_issues) + ' issues found', '1')}"
        f"  —  {_c(f'High: {high}', '31')}"
        f" | {_c(f'Medium: {med}', '33')}"
        f" | {_c(f'Low: {low}', '32')}"
    )
    if trend:
        td = trend['total_issues_delta']
        if td != 0:
            sign = '+' if td > 0 else ''
            issue_line += f"  ({sign}{td} from baseline)"
    print(issue_line)
    if schema_count:
        print(f"  Schema violations: {_c(str(schema_count), '31')}")
    print()
