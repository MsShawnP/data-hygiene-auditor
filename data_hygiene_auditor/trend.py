"""Trend analysis — compare current audit against a previous baseline."""

import json
from collections import Counter


def load_baseline(path):
    """Load a previous audit result from a JSON file."""
    with open(path) as f:
        return json.load(f)


def compute_trend(current, baseline):
    """Compare current audit results against a baseline.

    Returns a trend dict with score deltas and issue count changes.
    """
    trend = {
        'baseline_file': baseline.get('input_file', 'unknown'),
        'baseline_timestamp': baseline.get('audit_timestamp', 'unknown'),
        'overall_score_previous': baseline.get('overall_score', 0),
        'overall_score_delta': (
            current.get('overall_score', 0)
            - baseline.get('overall_score', 0)
        ),
    }

    current_counts = _count_issues(current)
    baseline_counts = _count_issues(baseline)

    trend['total_issues_previous'] = baseline_counts['total']
    trend['total_issues_delta'] = (
        current_counts['total'] - baseline_counts['total']
    )
    trend['severity_previous'] = {
        'High': baseline_counts['High'],
        'Medium': baseline_counts['Medium'],
        'Low': baseline_counts['Low'],
    }
    trend['severity_deltas'] = {
        'High': current_counts['High'] - baseline_counts['High'],
        'Medium': current_counts['Medium'] - baseline_counts['Medium'],
        'Low': current_counts['Low'] - baseline_counts['Low'],
    }

    trend['sheets'] = {}
    all_sheets = (
        set(current.get('sheets', {}).keys())
        | set(baseline.get('sheets', {}).keys())
    )

    for sheet_name in sorted(all_sheets):
        curr_sheet = current.get('sheets', {}).get(sheet_name)
        base_sheet = baseline.get('sheets', {}).get(sheet_name)

        if curr_sheet and base_sheet:
            curr_issues = _count_sheet_issues(curr_sheet)
            base_issues = _count_sheet_issues(base_sheet)
            trend['sheets'][sheet_name] = {
                'status': 'compared',
                'score_previous': base_sheet.get('health_score', 0),
                'score_delta': (
                    curr_sheet.get('health_score', 0)
                    - base_sheet.get('health_score', 0)
                ),
                'issues_previous': base_issues['total'],
                'issues_delta': (
                    curr_issues['total'] - base_issues['total']
                ),
            }
        elif curr_sheet:
            trend['sheets'][sheet_name] = {'status': 'new'}
        else:
            trend['sheets'][sheet_name] = {'status': 'removed'}

    return trend


def _count_issues(results):
    """Count total and per-severity issues across all sheets."""
    counts: Counter[str] = Counter()
    for sheet_data in results.get('sheets', {}).values():
        counts += _count_sheet_issues(sheet_data)
    return counts


def _count_sheet_issues(sheet_data):
    """Count issues in a single sheet."""
    counts: Counter[str] = Counter()
    for field_data in sheet_data.get('fields', {}).values():
        for issue in field_data.get('issues', []):
            counts['total'] += 1
            counts[issue.get('severity', 'Medium')] += 1
    for dup in sheet_data.get('phantom_duplicates', []):
        counts['total'] += 1
        counts[dup.get('severity', 'Medium')] += 1
    for fuzz in sheet_data.get('fuzzy_duplicates', []):
        counts['total'] += 1
        counts[fuzz.get('severity', 'Medium')] += 1
    for sv in sheet_data.get('schema_violations', []):
        counts['total'] += 1
        counts[sv.get('severity', 'Medium')] += 1
    return counts
