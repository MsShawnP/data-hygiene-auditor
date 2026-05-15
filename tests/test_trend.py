"""Tests for trend analysis."""

import json

import pandas as pd

from data_hygiene_auditor.core import run_audit
from data_hygiene_auditor.trend import compute_trend, load_baseline


def _make_results(overall_score, sheets):
    """Build a minimal results dict for trend tests."""
    results = {
        'input_file': 'test.csv',
        'audit_timestamp': '2025-01-01 00:00:00',
        'overall_score': overall_score,
        'sheets': {},
    }
    for name, score, issues in sheets:
        fields = {}
        for itype, severity in issues:
            col = f"col_{len(fields)}"
            fields[col] = {
                'inferred_type': 'freetext',
                'null_analysis': {
                    'missing_pct': 0, 'null_count': 0,
                    'blank_count': 0, 'whitespace_only': 0,
                    'total_missing': 0, 'total_rows': 10,
                },
                'issues': [{
                    'type': itype,
                    'severity': severity,
                    'detail': {},
                    'why': '',
                }],
            }
        results['sheets'][name] = {
            'health_score': score,
            'row_count': 10,
            'col_count': len(fields),
            'fields': fields,
            'phantom_duplicates': [],
            'fuzzy_duplicates': [],
            'schema_violations': [],
        }
    return results


class TestComputeTrend:
    def test_score_improvement(self):
        baseline = _make_results(60, [
            ('Sheet1', 60, [('mixed_format', 'High')] * 5),
        ])
        current = _make_results(85, [
            ('Sheet1', 85, [('mixed_format', 'Low')] * 2),
        ])
        trend = compute_trend(current, baseline)
        assert trend['overall_score_delta'] == 25
        assert trend['overall_score_previous'] == 60
        assert trend['total_issues_delta'] == -3

    def test_score_decline(self):
        baseline = _make_results(90, [
            ('Sheet1', 90, [('null_analysis', 'Low')]),
        ])
        current = _make_results(70, [
            ('Sheet1', 70, [('mixed_format', 'High')] * 4),
        ])
        trend = compute_trend(current, baseline)
        assert trend['overall_score_delta'] == -20
        assert trend['total_issues_delta'] == 3

    def test_no_change(self):
        data = _make_results(80, [
            ('Sheet1', 80, [('null_analysis', 'Medium')] * 3),
        ])
        trend = compute_trend(data, data)
        assert trend['overall_score_delta'] == 0
        assert trend['total_issues_delta'] == 0

    def test_severity_deltas(self):
        baseline = _make_results(70, [
            ('S', 70, [
                ('a', 'High'), ('b', 'High'),
                ('c', 'Medium'), ('d', 'Low'),
            ]),
        ])
        current = _make_results(80, [
            ('S', 80, [('a', 'High'), ('c', 'Low')]),
        ])
        trend = compute_trend(current, baseline)
        assert trend['severity_deltas']['High'] == -1
        assert trend['severity_deltas']['Medium'] == -1
        assert trend['severity_deltas']['Low'] == 0

    def test_new_sheet(self):
        baseline = _make_results(80, [
            ('Sheet1', 80, []),
        ])
        current = _make_results(75, [
            ('Sheet1', 80, []),
            ('Sheet2', 70, [('a', 'High')]),
        ])
        trend = compute_trend(current, baseline)
        assert trend['sheets']['Sheet1']['status'] == 'compared'
        assert trend['sheets']['Sheet2']['status'] == 'new'

    def test_removed_sheet(self):
        baseline = _make_results(75, [
            ('Sheet1', 80, []),
            ('Sheet2', 70, []),
        ])
        current = _make_results(80, [
            ('Sheet1', 80, []),
        ])
        trend = compute_trend(current, baseline)
        assert trend['sheets']['Sheet2']['status'] == 'removed'

    def test_per_sheet_deltas(self):
        baseline = _make_results(70, [
            ('S1', 60, [('a', 'High')] * 3),
        ])
        current = _make_results(85, [
            ('S1', 85, [('a', 'Low')]),
        ])
        trend = compute_trend(current, baseline)
        assert trend['sheets']['S1']['score_delta'] == 25
        assert trend['sheets']['S1']['issues_delta'] == -2


class TestLoadBaseline:
    def test_loads_json(self, tmp_path):
        data = {'overall_score': 75, 'sheets': {}}
        path = tmp_path / "baseline.json"
        path.write_text(json.dumps(data))
        loaded = load_baseline(str(path))
        assert loaded['overall_score'] == 75


class TestTrendIntegration:
    def test_trend_in_run_audit(self, tmp_path):
        df = pd.DataFrame({
            'Phone': ['(555) 123-4567', '555-234-5678'],
        })
        csv_path = tmp_path / "data.csv"
        df.to_csv(str(csv_path), index=False)

        results1 = run_audit(str(csv_path))

        baseline_path = tmp_path / "baseline.json"
        with open(str(baseline_path), 'w') as f:
            json.dump(results1, f, default=str)

        results2 = run_audit(
            str(csv_path), baseline_path=str(baseline_path),
        )
        assert 'trend' in results2
        assert results2['trend']['overall_score_delta'] == 0

    def test_trend_shows_improvement(self, tmp_path):
        df_bad = pd.DataFrame({
            'Phone': ['test', 'N/A', 'TBD', 'bad', 'worse'],
        })
        csv_bad = tmp_path / "bad.csv"
        df_bad.to_csv(str(csv_bad), index=False)
        results_bad = run_audit(str(csv_bad))

        baseline_path = tmp_path / "baseline.json"
        with open(str(baseline_path), 'w') as f:
            json.dump(results_bad, f, default=str)

        df_good = pd.DataFrame({
            'Phone': [
                '(555) 123-4567', '(555) 234-5678',
                '(555) 345-6789', '(555) 456-7890',
                '(555) 567-8901',
            ],
        })
        csv_good = tmp_path / "good.csv"
        df_good.to_csv(str(csv_good), index=False)

        results_good = run_audit(
            str(csv_good), baseline_path=str(baseline_path),
        )
        assert results_good['trend']['overall_score_delta'] > 0
        assert results_good['trend']['total_issues_delta'] < 0
