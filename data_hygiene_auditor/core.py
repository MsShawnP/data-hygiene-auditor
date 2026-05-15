"""Core audit orchestrator and data loading."""

import os
from datetime import datetime
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


def _load_sheets(input_path):
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


def run_audit(input_path):
    """Run all checks against an Excel or CSV file. Returns structured audit results."""
    sheets = _load_sheets(input_path)
    results = {
        'input_file': os.path.basename(input_path),
        'audit_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sheets': {},
    }

    for sheet_name, df in sheets.items():
        if df.empty:
            continue

        sheet_results = {
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
                field_findings['issues'].append({
                    'type': 'null_analysis',
                    'severity': null_severity,
                    'detail': null_info,
                    'why': WHY_IT_MATTERS['null_analysis'],
                })

            if mixed:
                sev = rate_severity('mixed_format', mixed)
                why_key = f'mixed_format_{field_type}'
                field_findings['issues'].append({
                    'type': 'mixed_format',
                    'severity': sev,
                    'detail': mixed,
                    'why': WHY_IT_MATTERS.get(
                        why_key,
                        f'Mixed {field_type} formats reduce data consistency'
                        ' and can cause errors in downstream processing.',
                    ),
                })

            for w in wrong:
                field_findings['issues'].append({
                    'type': 'wrong_purpose',
                    'severity': rate_severity('wrong_purpose', w),
                    'detail': w,
                    'why': WHY_IT_MATTERS['wrong_purpose'],
                })

            for p in placeholders:
                ptype = p.get('type', 'placeholder')
                sev = rate_severity('placeholder', p)
                why_key = (
                    'suspicious_repetition'
                    if ptype == 'suspicious_repetition'
                    else 'placeholder'
                )
                field_findings['issues'].append({
                    'type': ptype,
                    'severity': sev,
                    'detail': p,
                    'why': WHY_IT_MATTERS[why_key],
                })

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
        sheet_results['phantom_duplicates'] = dupes

        phantom_row_sets = [
            frozenset(i - 2 for i in d['rows'])
            for d in dupes
        ]
        fuzzy = analyze_fuzzy_duplicates(
            df, sheet_name, field_types,
            phantom_row_sets=phantom_row_sets,
        )
        for f in fuzzy:
            f['severity'] = rate_severity('fuzzy_duplicate', f)
            f['why'] = WHY_IT_MATTERS['fuzzy_duplicate']
        sheet_results['fuzzy_duplicates'] = fuzzy

        sheet_results['health_score'] = _compute_health_score(
            sheet_results,
        )
        results['sheets'][sheet_name] = sheet_results

    if results['sheets']:
        scores = [s['health_score'] for s in results['sheets'].values()]
        results['overall_score'] = round(sum(scores) / len(scores))
    else:
        results['overall_score'] = 100

    return results


def _compute_health_score(sheet_data):
    """Compute a 0-100 health score for a sheet.

    Starts at 100 and deducts for issues found. Designed so:
    90+ = clean, 70-89 = needs attention, <70 = significant issues.
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

    return max(0, round(score))
