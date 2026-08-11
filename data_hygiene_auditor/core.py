"""Core audit orchestrator and data loading."""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .detection import (
    analyze_fuzzy_duplicates,
    analyze_mixed_formats,
    analyze_nulls,
    analyze_phantom_duplicates,
    analyze_placeholders,
    analyze_wrong_purpose,
    infer_field_type,
    rate_severity,
)
from .schema import validate_schema
from .suggestions import generate_dup_fix, generate_fix
from .trend import compute_trend, load_baseline

HIGH = 'High'
MEDIUM = 'Medium'
LOW = 'Low'


def _report_timestamp() -> str:
    """Timestamp shown in the report header/footer and findings workbook.

    Honors SOURCE_DATE_EPOCH (the reproducible-builds standard): when set, the
    timestamp is derived from that UTC epoch so regenerated deliverables are
    byte-reproducible; otherwise it is the current wall-clock time. The report
    also emits per-field `data-severities` in a fixed High>Medium>Low order —
    together these are the two nondeterminism sources noted in DECISIONS.md
    (2026-08-07); a bare `datetime.now()` here defeats any byte-lock on the
    output regardless of PYTHONHASHSEED.
    """
    sde = os.environ.get('SOURCE_DATE_EPOCH')
    if sde:
        return datetime.fromtimestamp(int(sde), tz=timezone.utc).strftime(
            '%Y-%m-%d %H:%M:%S')
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


WHY_IT_MATTERS = {
    'mixed_format_date': (
        "Mixed date formats cause sorting failures, broken filters, and incorrect calculations. "
        "A date stored as text (\"Jan 15, 2023\") won't sort chronologically next to \"2023-01-15\". "
        "Downstream tools, APIs, and reports will misparse or reject inconsistent dates."
    ),
    'mixed_format_phone': (
        "Inconsistent phone formats break deduplication, prevent reliable search/lookup, and cause "
        "issues with automated dialers or SMS systems. Two records for the same person may appear "
        "as different contacts if one says \"(555) 123-4567\" and another says \"5551234567\"."
    ),
    'mixed_format_currency': (
        "Mixed currency formats (\"$1,250.00\" vs \"1250\" vs \"five thousand\") prevent accurate "
        "aggregation and comparison. Summing a column with text-formatted currency returns errors or "
        "silently drops values, leading to wrong totals in financial reports."
    ),
    'mixed_format_id': (
        "Inconsistent ID formats break joins, lookups, and deduplication — a key stored as "
        "\"CUST-001\" won't match \"1027\", so related records silently fail to link."
    ),
    'wrong_purpose': (
        "When a field is used for something other than its intended purpose — like storing reference "
        "codes in a name field or text in a currency field — it corrupts both the misused field and "
        "whatever field should have held that data. This makes the data unreliable for any analysis."
    ),
    'placeholder': (
        "Placeholder values (\"Test\", \"N/A\", \"TBD\") that persist in production data inflate counts, "
        "skew averages, and create phantom records. They often indicate incomplete data entry or "
        "inadequate validation at the point of capture."
    ),
    'suspicious_repetition': (
        "When the same value appears far more often than expected, it may indicate a default value "
        "that was never updated, a copy-paste error, or a system glitch that stamped the same data "
        "across multiple records."
    ),
    'phantom_duplicate': (
        "These records look different on the surface (different casing, extra spaces, punctuation "
        "variations) but represent the same entity. They cause inflated counts, split transaction "
        "histories, and duplicate outreach — problems that compound over time."
    ),
    'fuzzy_duplicate': (
        "These records are not exact matches but are similar enough to likely represent the same "
        "entity — differing only by typos, abbreviations, or word reordering (e.g. \"Jon Smith\" vs "
        "\"John Smith\", \"St.\" vs \"Street\"). Fuzzy duplicates are harder to catch but cause the "
        "same problems as exact duplicates: inflated counts, split histories, and wasted outreach."
    ),
    'exact_duplicate': (
        "Exact duplicate rows are the clearest sign of a data quality issue — they can result from "
        "double-submissions, ETL failures, or missing unique constraints. Every duplicate inflates "
        "counts and distorts any metric built on this data."
    ),
    'null_analysis': (
        "High rates of missing data reduce the reliability of any analysis built on this field. "
        "Missing values can skew averages, break joins between tables, and cause downstream systems "
        "to error out or produce incomplete results."
    ),
}

SUPPORTED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.tsv'}

# Leading characters that spreadsheet applications (Excel, LibreOffice,
# Google Sheets) will interpret as the start of a formula when opening an
# xlsx or CSV file.
_FORMULA_TRIGGERS = ('=', '+', '-', '@', '\t', '\r')


def sanitize_spreadsheet_cell(value):
    """Neutralize spreadsheet formula injection in a cell value.

    User-supplied text — sheet names, column headers, and echoed cell
    values from the audited file — is written into the Excel findings file
    and the remediation CSV. A spreadsheet app evaluates any cell whose
    text begins with ``=``, ``+``, ``-``, ``@``, or a tab/CR as a formula,
    so a column named ``=HYPERLINK(...)`` would execute when a recipient
    opens the "email-ready" deliverable. Prefixing a single quote forces
    the value to be treated as literal text. Non-string values (ints,
    floats, ``None``) pass through unchanged.
    """
    if isinstance(value, str) and value[:1] in _FORMULA_TRIGGERS:
        return "'" + value
    return value


def issue_headline(
    issue_type: str, detail: dict, issue: dict | None = None,
) -> tuple[str, str]:
    """Return the ``(label, detail_text)`` for an issue's one-line headline.

    ``label`` is the emphasized lead (bolded in the HTML report, bracketed
    in the PDF); ``detail_text`` is the remainder of the sentence and may be
    empty. This is the SINGLE source of the per-issue-type wording shared by
    the HTML, PDF, Excel, and API outputs — add or rename an issue type here
    and every renderer stays in sync. Renderers add their own markup and any
    type-specific extras (format-distribution table, example lists).
    """
    issue = issue or {}
    if issue_type == 'mixed_format':
        total = (
            detail.get('dominant_count', 0) + detail.get('inconsistent_count', 0)
        )
        return (
            f"Mixed {detail.get('field_type', '')} formats",
            f"{detail.get('inconsistent_count', 0)} of {total} values"
            f" deviate from {detail.get('dominant_format', '')}",
        )
    if issue_type == 'wrong_purpose':
        example = detail.get('example')
        return (
            str(detail.get('issue', 'Wrong purpose')),
            f'e.g. "{example}"' if example else '',
        )
    if issue_type in ('placeholder_value', 'placeholder'):
        return (
            'Placeholder',
            f'"{detail.get("value", "")}" appears'
            f' {detail.get("count", 0)} times ({detail.get("pct", 0)}%)',
        )
    if issue_type == 'suspicious_repetition':
        return (
            'Suspicious repetition',
            f'"{detail.get("value", "")}" appears'
            f' {detail.get("count", 0)} times ({detail.get("pct", 0)}%)',
        )
    if issue_type == 'null_analysis':
        return (
            'High missing rate',
            f'{detail.get("total_missing", 0)} of'
            f' {detail.get("total_rows", 0)} values missing'
            f' ({detail.get("missing_pct", 0)}%)',
        )
    if issue_type == 'custom_rule':
        return (
            str(issue.get('rule_name', 'Custom Rule')),
            str(detail.get('message', '')),
        )
    return (str(issue_type), '')


# Issue types with a dedicated headline in issue_headline(); anything else
# falls back to a raw dump of the detail dict in the renderers.
KNOWN_ISSUE_TYPES = frozenset({
    'mixed_format', 'wrong_purpose', 'placeholder_value', 'placeholder',
    'suspicious_repetition', 'null_analysis', 'custom_rule',
})


def describe_issue(issue_type: str, detail: dict, issue: dict | None = None) -> str:
    """Return a plain-text one-line description for an issue."""
    label, detail_text = issue_headline(issue_type, detail, issue)
    return f"{label}: {detail_text}" if detail_text else label


def issue_example(issue_type: str, detail: dict, issue: dict | None = None) -> str:
    """Return a plain-text example/detail string for an issue."""
    if issue_type == 'mixed_format':
        return '; '.join(
            f"{k}: {v}"
            for k, v in detail.get('format_distribution', {}).items()
        )
    if issue_type == 'wrong_purpose':
        return str(detail.get('example', ''))
    if issue_type in ('placeholder_value', 'placeholder'):
        return f"{detail.get('pct', 0)}% of non-null values"
    if issue_type == 'suspicious_repetition':
        return f"{detail.get('pct', 0)}% of non-null values"
    if issue_type == 'null_analysis':
        return (
            f"Null: {detail.get('null_count', 0)},"
            f" Blank: {detail.get('blank_count', 0)},"
            f" Whitespace: {detail.get('whitespace_only', 0)}"
        )
    if issue_type == 'custom_rule':
        rule_name = (issue or {}).get('rule_name', 'Custom Rule')
        msg = detail.get('message', '')
        examples = detail.get('examples', [])
        example_str = '; '.join(str(e) for e in examples[:5])
        return f"{rule_name}: {msg} — {example_str}" if example_str else f"{rule_name}: {msg}"
    import json
    return json.dumps(detail, default=str)


def describe_schema_violation(sv: dict) -> str:
    """Return a plain-text description for a schema violation."""
    svtype = sv['type']
    detail = sv.get('detail', {})
    col = sv.get('column', '') or detail.get('column', '')
    if svtype == 'schema_type_mismatch':
        return (
            f"Expected type '{detail.get('expected_type', '')}'"
            f" but inferred '{detail.get('actual_type', '')}'"
        )
    if svtype == 'schema_missing_column':
        return f"Required column '{detail.get('expected_column', col)}' missing"
    if svtype == 'schema_completeness_violation':
        return (
            f"{detail.get('actual_missing_pct', 0)}% missing"
            f" (max {detail.get('max_missing_pct', 0)}%)"
        )
    return str(svtype)


# Health-score bands. The threshold boundaries live here and nowhere else;
# every renderer keys its colours/labels off the band name from score_band()
# rather than re-testing 90/70/40, so the bands cannot drift between the CLI,
# HTML, and PDF outputs.
_SCORE_BAND_LABELS = {
    'clean': 'Clean',
    'attention': 'Needs Attention',
    'significant': 'Significant Issues',
    'critical': 'Critical',
}


def score_band(score: int | float) -> str:
    """Return the band key ('clean'/'attention'/'significant'/'critical')."""
    if score >= 90:
        return 'clean'
    if score >= 70:
        return 'attention'
    if score >= 40:
        return 'significant'
    return 'critical'


def score_label(score: int | float) -> str:
    """Return a human-readable label for a health score."""
    return _SCORE_BAND_LABELS[score_band(score)]


def count_sheet_issues(sheet_data):
    """Count issues in a single sheet across every source.

    Tallies field issues, phantom duplicates, fuzzy duplicates, and schema
    violations into a Counter with keys 'total', per-severity ('High' /
    'Medium' / 'Low'), and 'schema' (the number of schema violations). This
    is the single per-sheet counter shared by count_issues (summed across
    sheets) and the trend comparison, so the two cannot drift apart.
    """
    counts: Counter[str] = Counter()
    for field_data in sheet_data.get('fields', {}).values():
        for issue in field_data.get('issues', []):
            counts['total'] += 1
            counts[issue['severity']] += 1
    for dup in sheet_data.get('phantom_duplicates', []):
        counts['total'] += 1
        counts[dup['severity']] += 1
    for fuzz in sheet_data.get('fuzzy_duplicates', []):
        counts['total'] += 1
        counts[fuzz['severity']] += 1
    for sv in sheet_data.get('schema_violations', []):
        counts['total'] += 1
        counts[sv['severity']] += 1
        counts['schema'] += 1
    return counts


def count_issues(results):
    """Count total and per-severity issues across all sheets.

    Counts all issue sources: field issues, phantom duplicates,
    fuzzy duplicates, and schema violations.

    Returns dict with keys: 'total', 'High', 'Medium', 'Low', 'schema'.
    """
    totals: Counter[str] = Counter()
    for sheet in results['sheets'].values():
        totals.update(count_sheet_issues(sheet))
    result = dict(totals)
    result.setdefault('schema', 0)
    return result


def load_sheets(input_path):
    """Load tabular data as a dict of {sheet_name: DataFrame}."""
    ext = Path(input_path).suffix.lower()
    if ext in ('.csv', '.tsv'):
        sep = '\t' if ext == '.tsv' else ','
        df = pd.read_csv(input_path, dtype=str, sep=sep)
        return {Path(input_path).stem: df}
    else:
        xls = pd.ExcelFile(input_path)
        return {
            name: pd.read_excel(xls, sheet_name=name, dtype=str)
            for name in xls.sheet_names
        }


def run_audit(input_path, fuzzy_threshold=0.85, schema_path=None, baseline_path=None, rules_path=None, sheets=None):
    """Run all checks against an Excel or CSV file. Returns structured audit results."""
    schema = None
    if schema_path:
        from .schema import load_schema
        schema = load_schema(schema_path)

    rules = None
    if rules_path:
        from .rules import evaluate_rule, load_rules
        rules = load_rules(rules_path)

    if sheets is None:
        sheets = load_sheets(input_path)
    results = {
        'input_file': os.path.basename(input_path),
        'audit_timestamp': _report_timestamp(),
        'sheets': {},
    }

    for sheet_name, df in sheets.items():
        if df.empty:
            results.setdefault('warnings', []).append({
                'type': 'empty_sheet',
                'sheet': sheet_name,
                'message': (
                    f"Sheet '{sheet_name}' has no data rows and was skipped."
                ),
            })
            continue

        sheet_results: dict = {
            'row_count': len(df),
            'col_count': len(df.columns),
            'fields': {},
            'phantom_duplicates': [],
        }

        for col in df.columns:
            field_type = infer_field_type(col, df[col].values)
            null_info = analyze_nulls(df[col])
            mixed = analyze_mixed_formats(df[col], field_type)
            wrong = analyze_wrong_purpose(df[col], col, field_type)
            placeholders = analyze_placeholders(df[col], col)

            field_findings = {
                'inferred_type': field_type,
                'null_analysis': null_info,
                'issues': [],
            }

            null_severity = rate_severity('null_analysis', null_info)
            if null_severity:
                issue = {
                    'type': 'null_analysis',
                    'severity': null_severity,
                    'detail': null_info,
                    'why': WHY_IT_MATTERS['null_analysis'],
                }
                fix = generate_fix('null_analysis', null_info, col, field_type)
                if fix:
                    issue['fix'] = fix
                field_findings['issues'].append(issue)

            if mixed:
                sev = rate_severity('mixed_format', mixed)
                why_key = f'mixed_format_{field_type}'
                issue = {
                    'type': 'mixed_format',
                    'severity': sev,
                    'detail': mixed,
                    'why': WHY_IT_MATTERS.get(
                        why_key,
                        f'Mixed {field_type} formats reduce data consistency'
                        ' and can cause errors in downstream processing.',
                    ),
                }
                fix = generate_fix('mixed_format', mixed, col, field_type)
                if fix:
                    issue['fix'] = fix
                field_findings['issues'].append(issue)

            for w in wrong:
                why_key = (
                    'mixed_format_id'
                    if w.get('issue') == 'Mixed ID formats'
                    else 'wrong_purpose'
                )
                issue = {
                    'type': 'wrong_purpose',
                    'severity': rate_severity('wrong_purpose', w),
                    'detail': w,
                    'why': WHY_IT_MATTERS[why_key],
                }
                fix = generate_fix('wrong_purpose', w, col, field_type)
                if fix:
                    issue['fix'] = fix
                field_findings['issues'].append(issue)

            for p in placeholders:
                ptype = p.get('type', 'placeholder')
                sev = rate_severity('placeholder', p)
                why_key = (
                    'suspicious_repetition'
                    if ptype == 'suspicious_repetition'
                    else 'placeholder'
                )
                issue = {
                    'type': ptype,
                    'severity': sev,
                    'detail': p,
                    'why': WHY_IT_MATTERS[why_key],
                }
                fix = generate_fix(ptype, p, col, field_type)
                if fix:
                    issue['fix'] = fix
                field_findings['issues'].append(issue)

            if rules:
                for rule in rules:
                    finding = evaluate_rule(rule, df[col], col)
                    if finding:
                        field_findings['issues'].append(finding)

            field_findings['profile'] = _compute_profile(df[col], field_type)
            sheet_results['fields'][col] = field_findings

        field_types = {
            col: fd['inferred_type']
            for col, fd in sheet_results['fields'].items()
        }
        dupes = analyze_phantom_duplicates(df, sheet_name, field_types)
        for d in dupes:
            d['severity'] = rate_severity('phantom_duplicate', d)
            d['why'] = WHY_IT_MATTERS.get(
                d['type'], WHY_IT_MATTERS['phantom_duplicate']
            )
            fix = generate_dup_fix(d['type'], d, sheet_name)
            if fix:
                d['fix'] = fix
        sheet_results['phantom_duplicates'] = dupes

        phantom_row_sets = [
            frozenset(i - 2 for i in d['rows'])
            for d in dupes
        ]
        fuzzy_raw = analyze_fuzzy_duplicates(
            df, sheet_name, field_types,
            threshold=fuzzy_threshold,
            phantom_row_sets=phantom_row_sets,
        )
        fuzzy = []
        for f in fuzzy_raw:
            if f.get('type') == '_levenshtein_skipped':
                results.setdefault('warnings', []).append({
                    'type': 'levenshtein_skipped',
                    'sheet': sheet_name,
                    'unmatched_rows': f['unmatched_count'],
                    'limit': f['limit'],
                    'message': (
                        f"Fuzzy (Levenshtein) matching skipped for sheet"
                        f" '{sheet_name}': {f['unmatched_count']} unmatched"
                        f" rows exceeds the {f['limit']}-row limit."
                    ),
                })
                continue
            f['severity'] = rate_severity('fuzzy_duplicate', f)
            f['why'] = WHY_IT_MATTERS['fuzzy_duplicate']
            fix = generate_dup_fix('fuzzy_duplicate', f, sheet_name)
            if fix:
                f['fix'] = fix
            fuzzy.append(f)
        sheet_results['fuzzy_duplicates'] = fuzzy

        if schema:
            sheet_results['schema_violations'] = validate_schema(
                sheet_results, schema, sheet_name,
            )
        else:
            sheet_results['schema_violations'] = []

        sheet_results['health_score'] = _compute_health_score(
            sheet_results,
        )
        results['sheets'][sheet_name] = sheet_results

    if results['sheets']:
        scores = [s['health_score'] for s in results['sheets'].values()]
        results['overall_score'] = round(sum(scores) / len(scores))
    else:
        # Nothing was audited (every sheet was empty). A perfect score here
        # would falsely read as "Clean", so flag it explicitly and mark the
        # score as not meaningful rather than silently reporting 100.
        results['overall_score'] = 100
        results['audited'] = False
        results.setdefault('warnings', []).append({
            'type': 'nothing_audited',
            'message': (
                "No non-empty sheets were found — nothing was audited, so"
                " the health score is not meaningful."
            ),
        })

    if schema:
        results['schema'] = {'source': schema_path, 'validated': True}

    if rules:
        results['rules'] = {
            'source': rules_path,
            'count': len(rules),
            'names': [r.name for r in rules],
        }

    if baseline_path:
        baseline = load_baseline(baseline_path)
        results['trend'] = compute_trend(results, baseline)

    return results


def _sheet_row_total(results):
    """Total data rows audited across all sheets of one file's results."""
    return sum(s['row_count'] for s in results['sheets'].values())


def combine_overall_score(file_results):
    """Combine per-file audit results into one row-weighted overall score.

    Each file's ``overall_score`` is weighted by the number of rows it
    contributed, so a large file counts for more than a tiny one. Returns
    100 when there are no rows to audit. This is the single definition of a
    combined multi-file score, shared by ``run_multi_audit`` and the CLI so
    the two entry points cannot drift apart.
    """
    total_rows = sum(_sheet_row_total(r) for r in file_results)
    if total_rows <= 0:
        return 100
    weighted = sum(
        r['overall_score'] * _sheet_row_total(r) for r in file_results
    ) / total_rows
    return round(weighted)


def run_multi_audit(input_paths, fuzzy_threshold=0.85, schema_path=None, rules_path=None):
    """Run audits across multiple files. Returns a combined results dict.

    The returned dict has:
    - 'files': mapping of filename -> per-file audit results
    - 'overall_score': weighted average by row count
    - 'total_files': number of files audited
    - 'total_rows': sum of rows across all files
    """
    file_results = {}
    for path in input_paths:
        results = run_audit(
            path,
            fuzzy_threshold=fuzzy_threshold,
            schema_path=schema_path,
            rules_path=rules_path,
        )
        file_results[os.path.basename(path)] = results

    total_rows = sum(_sheet_row_total(r) for r in file_results.values())

    return {
        'files': file_results,
        'overall_score': combine_overall_score(list(file_results.values())),
        'total_files': len(file_results),
        'total_rows': total_rows,
    }


def _compute_health_score(sheet_data):
    """Compute a health score for a sheet.

    Starts at 100 and deducts for issues found. Designed so:
    90+ = clean, 70-89 = needs attention, 40-69 = significant issues,
    <40 = critical. Scores at or above 25 are the raw 100-minus-penalties
    value; below 25, a soft-floor transform compresses catastrophic sheets
    toward a floor of 8 (never 0) while staying strictly monotonic.
    """
    score = 100.0

    severity_penalty = {'High': 3.0, 'Medium': 1.5, 'Low': 0.5}
    for field_data in sheet_data['fields'].values():
        for issue in field_data['issues']:
            score -= severity_penalty.get(issue['severity'], 1.0)

    missing_pcts = [
        fd['null_analysis']['missing_pct']
        for fd in sheet_data['fields'].values()
    ]
    if missing_pcts:
        avg_missing = sum(missing_pcts) / len(missing_pcts)
        score -= avg_missing * 0.2

    for dup in sheet_data['phantom_duplicates']:
        if dup['type'] == 'exact_duplicate':
            score -= 5.0
        else:
            score -= 3.0
        score -= severity_penalty.get(dup['severity'], 1.0)

    for fuzz in sheet_data.get('fuzzy_duplicates', []):
        score -= 1.5
        score -= severity_penalty.get(fuzz['severity'], 0.5)

    for sv in sheet_data.get('schema_violations', []):
        score -= severity_penalty.get(sv['severity'], 1.0)

    KNEE, FLOOR, SCALE = 25.0, 8.0, 40.0
    if score >= KNEE:
        final = score
    else:
        deficit = KNEE - score            # >= 0, unbounded
        final = KNEE - (KNEE - FLOOR) * deficit / (deficit + SCALE)
    return int(min(100, max(FLOOR, round(final))))


def _compute_profile(series, field_type):
    """Compute column-level statistics for profiling."""
    total = len(series)
    non_null = series.dropna()
    non_null_str = non_null.astype(str).str.strip()
    non_empty = non_null_str[non_null_str != '']

    cardinality = int(non_empty.nunique()) if len(non_empty) > 0 else 0
    uniqueness_pct = round(cardinality / len(non_empty) * 100, 1) if len(non_empty) > 0 else 0.0

    lengths = non_empty.str.len()
    profile = {
        'cardinality': cardinality,
        'uniqueness_pct': uniqueness_pct,
        'total_values': total,
        'non_empty_values': int(len(non_empty)),
        'min_length': int(lengths.min()) if len(lengths) > 0 else 0,
        'max_length': int(lengths.max()) if len(lengths) > 0 else 0,
        'avg_length': round(float(lengths.mean()), 1) if len(lengths) > 0 else 0.0,
    }

    if field_type == 'currency':
        numeric = pd.to_numeric(
            non_empty.str.replace(r'[$,£€]', '', regex=True),
            errors='coerce',
        ).dropna()
        # Only report a numeric range when a strong majority of values are
        # actually numeric; otherwise a single stray number produces a
        # meaningless "range 1027.0-1027.0".
        if len(non_empty) > 0 and len(numeric) / len(non_empty) >= 0.80:
            profile['min_value'] = round(float(numeric.min()), 2)
            profile['max_value'] = round(float(numeric.max()), 2)
            profile['mean_value'] = round(float(numeric.mean()), 2)
            profile['median_value'] = round(float(numeric.median()), 2)

    elif field_type == 'id':
        numeric = pd.to_numeric(non_empty, errors='coerce').dropna()
        # ID columns are frequently coded (CUST-001); only emit a numeric
        # range when the column is overwhelmingly bare numbers.
        if len(non_empty) > 0 and len(numeric) / len(non_empty) >= 0.80:
            profile['min_value'] = round(float(numeric.min()), 2)
            profile['max_value'] = round(float(numeric.max()), 2)
            profile['mean_value'] = round(float(numeric.mean()), 2)
            profile['median_value'] = round(float(numeric.median()), 2)

    return profile
