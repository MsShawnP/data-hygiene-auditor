"""CLI entrypoint for the Data Hygiene Auditor."""

import argparse
import json
import os
import sys
from pathlib import Path

from .core import SUPPORTED_EXTENSIONS, count_issues, run_audit
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


def _get_version():
    """Get package version from metadata."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version('data-hygiene-auditor')
    except PackageNotFoundError:
        return '1.0.0'


def _resolve_inputs(input_arg):
    """Resolve input argument to a list of supported file paths.

    Accepts: a single file, a directory, or a glob pattern.
    """
    import glob as glob_mod

    path = Path(input_arg)

    if path.is_file():
        ext = path.suffix.lower()
        if ext in SUPPORTED_EXTENSIONS:
            return [str(path)]
        return []

    if path.is_dir():
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(path.rglob(f'*{ext}'))
        return sorted(str(f) for f in files)

    expanded = glob_mod.glob(input_arg, recursive=True)
    return sorted(
        f for f in expanded
        if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS
    )


_SEVERITY_TO_SARIF = {
    'High': 'error',
    'Medium': 'warning',
    'Low': 'note',
}


def _generate_sarif(all_results, input_files):
    """Generate SARIF 2.1.0 output for GitHub Code Scanning."""
    results_list = []
    rules = []
    rule_ids = set()

    for results, input_path in zip(all_results, input_files):
        for sheet_name, sheet_data in results['sheets'].items():
            for col_name, field_data in sheet_data['fields'].items():
                for issue in field_data['issues']:
                    rule_id = issue['type']
                    if issue.get('rule_name'):
                        rule_id = f"custom/{issue['rule_name']}"
                    if rule_id not in rule_ids:
                        rule_ids.add(rule_id)
                        rules.append({
                            'id': rule_id,
                            'shortDescription': {
                                'text': issue.get('rule_name', issue['type']),
                            },
                            'fullDescription': {
                                'text': issue.get('why', ''),
                            },
                            'defaultConfiguration': {
                                'level': _SEVERITY_TO_SARIF.get(
                                    issue['severity'], 'note',
                                ),
                            },
                        })
                    detail = issue.get('detail', {})
                    msg = detail.get('message', '') if isinstance(detail, dict) else str(detail)
                    results_list.append({
                        'ruleId': rule_id,
                        'level': _SEVERITY_TO_SARIF.get(issue['severity'], 'note'),
                        'message': {
                            'text': (
                                f"[{sheet_name}] {col_name}: {msg}"
                                if msg else
                                f"[{sheet_name}] {col_name}: {issue['type']}"
                            ),
                        },
                        'locations': [{
                            'physicalLocation': {
                                'artifactLocation': {
                                    'uri': input_path.replace('\\', '/'),
                                },
                            },
                        }],
                    })

    return {
        '$schema': 'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json',
        'version': '2.1.0',
        'runs': [{
            'tool': {
                'driver': {
                    'name': 'data-hygiene-auditor',
                    'version': _get_version(),
                    'rules': rules,
                },
            },
            'results': results_list,
        }],
    }


def _export_remediation_csv(all_results, output_path):
    """Export a CSV remediation plan with one row per fixable issue."""
    import csv

    rows = []
    for results in all_results:
        source_file = results.get('input_file', '')
        for sheet_name, sheet_data in results['sheets'].items():
            for col_name, field_data in sheet_data['fields'].items():
                for issue in field_data['issues']:
                    fix = issue.get('fix', {})
                    detail = issue.get('detail', {})
                    msg = ''
                    if isinstance(detail, dict):
                        msg = detail.get('message', '')
                        if not msg and 'issue' in detail:
                            msg = detail['issue']
                    rows.append({
                        'File': source_file,
                        'Sheet': sheet_name,
                        'Field': col_name,
                        'Issue Type': issue.get('rule_name', issue['type']),
                        'Severity': issue['severity'],
                        'Description': msg,
                        'Fix Strategy': fix.get('strategy', '') if fix else '',
                        'Fix Code': fix.get('code', '') if fix else '',
                        'Assigned To': '',
                        'Status': 'Open',
                    })

            for dup in sheet_data['phantom_duplicates']:
                fix = dup.get('fix', {})
                rows.append({
                    'File': source_file,
                    'Sheet': sheet_name,
                    'Field': '(row-level)',
                    'Issue Type': dup['type'],
                    'Severity': dup['severity'],
                    'Description': f"{dup['group_size']} rows: {', '.join(str(r) for r in dup['rows'][:5])}",
                    'Fix Strategy': fix.get('strategy', '') if fix else '',
                    'Fix Code': fix.get('code', '') if fix else '',
                    'Assigned To': '',
                    'Status': 'Open',
                })

            for fuzz in sheet_data.get('fuzzy_duplicates', []):
                fix = fuzz.get('fix', {})
                rows.append({
                    'File': source_file,
                    'Sheet': sheet_name,
                    'Field': '(row-level)',
                    'Issue Type': 'fuzzy_duplicate',
                    'Severity': fuzz['severity'],
                    'Description': f"{fuzz['group_size']} rows: {', '.join(str(r) for r in fuzz['rows'][:5])}",
                    'Fix Strategy': fix.get('strategy', '') if fix else '',
                    'Fix Code': fix.get('code', '') if fix else '',
                    'Assigned To': '',
                    'Status': 'Open',
                })

    rows.sort(key=lambda r: {'High': 0, 'Medium': 1, 'Low': 2}.get(r['Severity'], 3))

    fieldnames = [
        'File', 'Sheet', 'Field', 'Issue Type', 'Severity',
        'Description', 'Fix Strategy', 'Fix Code',
        'Assigned To', 'Status',
    ]
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
        '--version', '-V', action='version',
        version=f'%(prog)s {_get_version()}',
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
    parser.add_argument(
        '--rules', '-r',
        help='Path to custom rules JSON for additional checks',
    )
    parser.add_argument(
        '--sarif',
        help='Output findings in SARIF format to the given path',
    )
    parser.add_argument(
        '--export-fixes',
        help='Export remediation plan as CSV to the given path',
    )
    parser.add_argument(
        '--quiet', '-q', action='store_true',
        help='Suppress all terminal output (just write report files)',
    )
    parser.add_argument(
        '--fail-under', type=int, default=0,
        help='Exit with code 1 if health score is below this threshold (0-100)',
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Process files exceeding the 2M row safety limit',
    )
    args = parser.parse_args()

    input_files = _resolve_inputs(args.input)
    if not input_files:
        print(
            f"Error: No supported files found for: {args.input}",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    def _log(msg=''):
        if not args.quiet:
            print(msg)

    from .core import _load_sheets
    ROW_WARN = 500_000
    ROW_LIMIT = 2_000_000

    _log(f"\n  {_c('Data Hygiene Auditor', '1')}")
    if len(input_files) > 1:
        _log(f"  Auditing {_c(str(len(input_files)) + ' files', '36')}\n")
    else:
        _log(f"  Auditing: {_c(input_files[0], '36')}\n")

    all_results = []
    for input_path in input_files:
        sheets_preview = _load_sheets(input_path)
        total_rows = sum(len(df) for df in sheets_preview.values())
        if total_rows > ROW_LIMIT and not args.force:
            print(
                f"Error: {input_path} has {total_rows:,} rows"
                f" (limit: {ROW_LIMIT:,})."
                f" Use --force to process anyway.",
                file=sys.stderr,
            )
            sys.exit(1)
        if total_rows > ROW_WARN:
            _log(
                f"  {_c('Warning:', '33')} Large file ({total_rows:,} rows)."
                f" Processing may be slow."
            )

        results = run_audit(
            input_path,
            fuzzy_threshold=args.threshold,
            schema_path=args.schema,
            baseline_path=args.baseline,
            rules_path=args.rules,
        )
        all_results.append(results)

        sheet_count = len(results['sheets'])
        file_label = (
            f"  {_c(Path(input_path).name, '1')} " if len(input_files) > 1 else ""
        )
        for i, (name, sdata) in enumerate(results['sheets'].items(), 1):
            score = sdata['health_score']
            score_color = '32' if score >= 90 else ('33' if score >= 70 else '31')
            _log(
                f"  {file_label}[{i}/{sheet_count}]"
                f" Analyzed sheet: {_c(name, '36')}"
                f"  (score: {_c(str(score), score_color)})"
            )

    for results in all_results:
        basename = Path(results['input_file']).stem
        html_path = os.path.join(
            args.output, f"{basename}_audit_report.html",
        )
        xlsx_path = os.path.join(
            args.output, f"{basename}_audit_findings.xlsx",
        )
        pdf_path = os.path.join(
            args.output, f"{basename}_audit_report.pdf",
        )

        if len(all_results) > 1:
            _log(f"\n  Reports for {_c(basename, '36')}:")
        else:
            _log("\n  Generating reports...")

        generate_html(results, html_path)
        _log(f"    {_c('HTML', '32')}  -> {html_path}")

        generate_excel(results, xlsx_path)
        _log(f"    {_c('Excel', '32')} -> {xlsx_path}")

        generate_pdf(results, pdf_path)
        _log(f"    {_c('PDF', '32')}   -> {pdf_path}")

        if args.json:
            json_path = os.path.join(
                args.output, f"{basename}_audit_results.json",
            )
            with open(json_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            _log(f"    {_c('JSON', '32')}  -> {json_path}")

    if args.generate_schema and all_results:
        from .schema import generate_schema
        schema_data = generate_schema(all_results[0])
        with open(args.generate_schema, 'w') as f:
            json.dump(schema_data, f, indent=2)
        _log(f"    {_c('Schema', '32')} -> {args.generate_schema}")

    if args.sarif:
        sarif_data = _generate_sarif(all_results, input_files)
        with open(args.sarif, 'w') as f:
            json.dump(sarif_data, f, indent=2)
        _log(f"    {_c('SARIF', '32')}  -> {args.sarif}")

    if args.export_fixes:
        _export_remediation_csv(all_results, args.export_fixes)
        _log(f"    {_c('Fixes', '32')} -> {args.export_fixes}")

    total_counts = {'total': 0, 'High': 0, 'Medium': 0, 'Low': 0, 'schema': 0}
    scores = []
    for results in all_results:
        counts = count_issues(results)
        for k in ('total', 'High', 'Medium', 'Low', 'schema'):
            total_counts[k] += counts.get(k, 0)
        scores.append(results['overall_score'])

    total_issues = total_counts['total']
    high = total_counts['High']
    med = total_counts['Medium']
    low = total_counts['Low']
    schema_count = total_counts['schema']

    overall = round(sum(scores) / len(scores)) if scores else 100
    score_color = '32' if overall >= 90 else ('33' if overall >= 70 else '31')

    score_str = f"{overall}/100"
    if len(all_results) == 1:
        trend = all_results[0].get('trend')
        if trend:
            delta = trend['overall_score_delta']
            arrow = _c(f'+{delta}', '32') if delta > 0 else _c(f'{delta}', '31') if delta < 0 else '='
            score_str += f" ({arrow} from baseline)"
    _log(
        f"\n  Health Score: {_c(score_str, score_color)}"
    )
    issue_line = (
        f"  {_c(str(total_issues) + ' issues found', '1')}"
        f"  —  {_c(f'High: {high}', '31')}"
        f" | {_c(f'Medium: {med}', '33')}"
        f" | {_c(f'Low: {low}', '32')}"
    )
    if len(all_results) == 1:
        trend = all_results[0].get('trend')
        if trend:
            td = trend['total_issues_delta']
            if td != 0:
                sign = '+' if td > 0 else ''
                issue_line += f"  ({sign}{td} from baseline)"
    _log(issue_line)
    if schema_count:
        _log(f"  Schema violations: {_c(str(schema_count), '31')}")
    for results in all_results:
        for w in results.get('warnings', []):
            _log(f"  {_c('Note:', '33')} {w['message']}")
    if len(all_results) > 1:
        _log(f"  Files audited: {len(all_results)}")
    _log()

    if args.fail_under and overall < args.fail_under:
        _log(
            f"  {_c('FAILED:', '31')} score {overall}"
            f" is below threshold {args.fail_under}"
        )
        sys.exit(1)
