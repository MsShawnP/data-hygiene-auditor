"""Integration and edge case tests."""
import json
import os
import tempfile
from pathlib import Path

from audit import generate_excel, generate_html, generate_pdf, load_sheets, run_audit
from data_hygiene_auditor.core import (
    _compute_health_score,
    combine_overall_score,
    count_issues,
    describe_issue,
    issue_headline,
    run_multi_audit,
    score_band,
    score_label,
)

SAMPLE_PATH = Path(__file__).parent.parent / "samples" / "input" / "sample_messy_data.xlsx"


class TestIntegration:
    def _tally(self, results):
        total = 0
        severity_totals = {"High": 0, "Medium": 0, "Low": 0}
        for sheet in results["sheets"].values():
            for field in sheet["fields"].values():
                for issue in field["issues"]:
                    total += 1
                    severity_totals[issue["severity"]] += 1
            for d in sheet["phantom_duplicates"]:
                total += 1
                severity_totals[d["severity"]] += 1
        return total, severity_totals

    def test_full_audit_issue_counts_are_consistent(self):
        # Structural invariants that hold regardless of threshold/rule tweaks:
        # the sample is deliberately messy, so it must surface issues at every
        # severity, and the total must equal the sum of the severity buckets.
        results = run_audit(str(SAMPLE_PATH))
        total, severity_totals = self._tally(results)
        assert total == sum(severity_totals.values())
        assert severity_totals["High"] > 0
        assert severity_totals["Medium"] > 0
        assert severity_totals["Low"] > 0

    def test_full_audit_matches_readme_snapshot(self):
        # Golden snapshot mirroring the figures quoted in README.md
        # ("59 issues — 23 High, 20 Medium, 16 Low"). This is EXPECTED to
        # churn when detection thresholds change; when it does, update both
        # this assertion and the README together so the docs never drift.
        results = run_audit(str(SAMPLE_PATH))
        total, severity_totals = self._tally(results)
        assert total == 59
        assert severity_totals["High"] == 23
        assert severity_totals["Medium"] == 20
        assert severity_totals["Low"] == 16

    def test_both_sheets_present(self):
        results = run_audit(str(SAMPLE_PATH))
        assert "Customers" in results["sheets"]
        assert "Orders" in results["sheets"]

    def test_health_scores_present(self):
        results = run_audit(str(SAMPLE_PATH))
        assert "overall_score" in results
        assert 0 <= results["overall_score"] <= 100
        for sheet in results["sheets"].values():
            assert "health_score" in sheet
            assert 0 <= sheet["health_score"] <= 100

    def test_messy_data_scores_low(self):
        results = run_audit(str(SAMPLE_PATH))
        assert results["overall_score"] < 70

    def test_html_report_generated(self):
        results = run_audit(str(SAMPLE_PATH))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_html(results, os.path.join(tmpdir, "report.html"))
            assert os.path.exists(path)
            content = Path(path).read_text(encoding="utf-8")
            assert "Data Hygiene Audit Report" in content
            assert "High" in content

    def test_excel_report_generated(self):
        results = run_audit(str(SAMPLE_PATH))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_excel(results, os.path.join(tmpdir, "findings.xlsx"))
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_pdf_report_generated(self):
        results = run_audit(str(SAMPLE_PATH))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_pdf(results, os.path.join(tmpdir, "report.pdf"))
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_field_types_inferred(self):
        results = run_audit(str(SAMPLE_PATH))
        customers = results["sheets"]["Customers"]
        fields = customers["fields"]
        assert fields["CustomerID"]["inferred_type"] == "id"
        assert fields["Email"]["inferred_type"] == "email"
        assert fields["Phone"]["inferred_type"] == "phone"
        assert fields["JoinDate"]["inferred_type"] == "date"
        assert fields["AccountBalance"]["inferred_type"] == "currency"
        assert fields["Status"]["inferred_type"] == "categorical"


class TestCSVSupport:
    def test_load_csv(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline="") as f:
            f.write("Name,Email,Phone\n")
            f.write("Alice,alice@test.com,(555) 123-4567\n")
            f.write("Bob,bob@test.com,555-234-5678\n")
            f.name
        try:
            sheets = load_sheets(f.name)
            assert len(sheets) == 1
            df = list(sheets.values())[0]
            assert len(df) == 2
            assert "Name" in df.columns
        finally:
            os.unlink(f.name)

    def test_csv_audit_produces_findings(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline="") as f:
            f.write("Name,Phone,JoinDate\n")
            f.write("Alice,(555) 123-4567,2023-01-15\n")
            f.write("Bob,555-234-5678,01/15/2023\n")
            f.write("Test,000-000-0000,N/A\n")
            f.name
        try:
            results = run_audit(f.name)
            sheets = results["sheets"]
            assert len(sheets) == 1
            sheet = list(sheets.values())[0]
            all_issues = []
            for field in sheet["fields"].values():
                all_issues.extend(field["issues"])
            assert len(all_issues) > 0
        finally:
            os.unlink(f.name)


class TestHealthScore:
    def test_clean_data_scores_high(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline="") as f:
            f.write("Name,Email,Phone\n")
            f.write("Alice,alice@test.com,(555) 123-4567\n")
            f.write("Bob,bob@test.com,(555) 234-5678\n")
            f.write("Charlie,charlie@test.com,(555) 345-6789\n")
        try:
            results = run_audit(f.name)
            assert results["overall_score"] >= 90
        finally:
            os.unlink(f.name)

    def test_score_never_negative(self):
        results = run_audit(str(SAMPLE_PATH))
        for sheet in results["sheets"].values():
            assert sheet["health_score"] >= 0

    def test_catastrophic_sheet_floors_in_single_digits(self):
        # A sheet with overwhelming penalties (raw score deeply negative)
        # should asymptote toward the soft floor: single digits, never 0 or below.
        sheet_data = {
            "fields": {},
            "phantom_duplicates": [
                {"type": "exact_duplicate", "severity": "High"}
                for _ in range(200)
            ],
            "fuzzy_duplicates": [],
            "schema_violations": [],
        }
        score = _compute_health_score(sheet_data)
        assert score > 0          # never floors to 0 or below
        assert score < 10         # catastrophic data lands in single digits


class TestEdgeCases:
    def test_single_row_sheet(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline="") as f:
            f.write("Name,Email\n")
            f.write("Alice,alice@test.com\n")
        try:
            results = run_audit(f.name)
            sheet = list(results["sheets"].values())[0]
            assert sheet["row_count"] == 1
        finally:
            os.unlink(f.name)

    def test_all_null_column(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline="") as f:
            f.write("Name,Empty\n")
            f.write("Alice,\n")
            f.write("Bob,\n")
            f.write("Charlie,\n")
        try:
            results = run_audit(f.name)
            sheet = list(results["sheets"].values())[0]
            empty_field = sheet["fields"]["Empty"]
            assert empty_field["null_analysis"]["missing_pct"] == 100.0
        finally:
            os.unlink(f.name)

    def test_tsv_support(self):
        with tempfile.NamedTemporaryFile(suffix=".tsv", mode="w", delete=False, newline="") as f:
            f.write("Name\tEmail\n")
            f.write("Alice\talice@test.com\n")
        try:
            results = run_audit(f.name)
            assert len(results["sheets"]) == 1
        finally:
            os.unlink(f.name)

    def test_empty_file_is_not_reported_clean(self):
        # Headers but zero data rows: nothing is audited, so the result must
        # be flagged rather than silently scored 100/"Clean".
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline="") as f:
            f.write("Name,Email\n")
        try:
            results = run_audit(f.name)
            assert results["sheets"] == {}
            assert results.get("audited") is False
            warning_types = {w["type"] for w in results.get("warnings", [])}
            assert "nothing_audited" in warning_types
        finally:
            os.unlink(f.name)


class TestCountIssues:
    def test_counts_all_issue_sources(self):
        results = run_audit(str(SAMPLE_PATH))
        counts = count_issues(results)
        assert counts['total'] == counts.get('High', 0) + counts.get('Medium', 0) + counts.get('Low', 0)
        assert counts['total'] > 0

    def test_matches_manual_count(self):
        results = run_audit(str(SAMPLE_PATH))
        counts = count_issues(results)
        manual_total = 0
        for sheet in results["sheets"].values():
            for field in sheet["fields"].values():
                manual_total += len(field["issues"])
            manual_total += len(sheet["phantom_duplicates"])
            manual_total += len(sheet.get("fuzzy_duplicates", []))
            manual_total += len(sheet.get("schema_violations", []))
        assert counts['total'] == manual_total

    def test_counts_fuzzy_duplicates(self):
        # Deterministic: a fuzzy duplicate contributes to both the grand
        # total and its severity bucket. (The messy sample's near-duplicates
        # are all caught as phantom duplicates, so it yields no standalone
        # fuzzy duplicates to exercise this against.)
        counts = count_issues({'sheets': {
            'Sheet1': {
                'fields': {},
                'phantom_duplicates': [],
                'fuzzy_duplicates': [
                    {'severity': 'Medium', 'type': 'fuzzy_duplicate'},
                ],
                'schema_violations': [],
            },
        }})
        assert counts['total'] == 1
        assert counts['Medium'] == 1

    def test_schema_count_tracked(self):
        counts = count_issues({'sheets': {
            'Sheet1': {
                'fields': {},
                'phantom_duplicates': [],
                'fuzzy_duplicates': [],
                'schema_violations': [
                    {'severity': 'High', 'type': 'schema_type_mismatch'},
                ],
            },
        }})
        assert counts['schema'] == 1
        assert counts['total'] == 1
        assert counts['High'] == 1


class TestCustomRulesIntegration:

    def test_rules_produce_findings(self, tmp_path):
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps({
            "rules": [{
                "name": "No short names",
                "description": "Names must be at least 10 characters",
                "severity": "Medium",
                "condition": "min_length",
                "threshold": 10,
                "column_pattern": "name",
            }]
        }))
        results = run_audit(str(SAMPLE_PATH), rules_path=str(rules_file))
        custom_findings = []
        for sheet in results['sheets'].values():
            for field_data in sheet['fields'].values():
                for issue in field_data['issues']:
                    if issue.get('type') == 'custom_rule':
                        custom_findings.append(issue)
        assert len(custom_findings) > 0
        assert custom_findings[0]['rule_name'] == "No short names"
        assert custom_findings[0]['severity'] == "Medium"

    def test_rules_counted_in_totals(self, tmp_path):
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps({
            "rules": [{
                "name": "All digits",
                "description": "IDs must be numeric",
                "severity": "High",
                "condition": "regex_match",
                "threshold": "^\\d+$",
                "column_pattern": ".*",
            }]
        }))
        results_without = run_audit(str(SAMPLE_PATH))
        results_with = run_audit(str(SAMPLE_PATH), rules_path=str(rules_file))
        count_without = count_issues(results_without)['total']
        count_with = count_issues(results_with)['total']
        assert count_with > count_without

    def test_rules_metadata_in_results(self, tmp_path):
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps({
            "rules": [{
                "name": "Test rule",
                "description": "d",
                "severity": "Low",
                "condition": "max_missing_pct",
                "threshold": 1,
            }]
        }))
        results = run_audit(str(SAMPLE_PATH), rules_path=str(rules_file))
        assert 'rules' in results
        assert results['rules']['count'] == 1
        assert results['rules']['names'] == ["Test rule"]

    def test_rules_affect_health_score(self, tmp_path):
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps({
            "rules": [{
                "name": "Strict rule",
                "description": "Everything fails",
                "severity": "High",
                "condition": "regex_match",
                "threshold": "^IMPOSSIBLE_VALUE$",
                "column_pattern": ".*",
            }]
        }))
        results_without = run_audit(str(SAMPLE_PATH))
        results_with = run_audit(str(SAMPLE_PATH), rules_path=str(rules_file))
        assert results_with['overall_score'] < results_without['overall_score']


class TestColumnProfiling:

    def test_profile_exists_for_all_fields(self):
        results = run_audit(str(SAMPLE_PATH))
        for sheet in results['sheets'].values():
            for col, field_data in sheet['fields'].items():
                assert 'profile' in field_data, f"Missing profile for {col}"
                profile = field_data['profile']
                assert 'cardinality' in profile
                assert 'uniqueness_pct' in profile
                assert 'min_length' in profile
                assert 'max_length' in profile
                assert 'avg_length' in profile

    def test_profile_cardinality(self):
        import pandas as pd

        from data_hygiene_auditor.core import _compute_profile
        series = pd.Series(["apple", "banana", "apple", "cherry", None])
        profile = _compute_profile(series, "freetext")
        assert profile['cardinality'] == 3
        assert profile['non_empty_values'] == 4
        assert profile['total_values'] == 5

    def test_profile_uniqueness(self):
        import pandas as pd

        from data_hygiene_auditor.core import _compute_profile
        series = pd.Series(["a", "b", "c", "d"])
        profile = _compute_profile(series, "freetext")
        assert profile['uniqueness_pct'] == 100.0

    def test_profile_lengths(self):
        import pandas as pd

        from data_hygiene_auditor.core import _compute_profile
        series = pd.Series(["hi", "hello", "hey"])
        profile = _compute_profile(series, "freetext")
        assert profile['min_length'] == 2
        assert profile['max_length'] == 5
        assert profile['avg_length'] == round((2 + 5 + 3) / 3, 1)

    def test_profile_numeric_stats_currency(self):
        import pandas as pd

        from data_hygiene_auditor.core import _compute_profile
        series = pd.Series(["$100.00", "$200.00", "$300.00", "$400.00"])
        profile = _compute_profile(series, "currency")
        assert profile['min_value'] == 100.0
        assert profile['max_value'] == 400.0
        assert profile['mean_value'] == 250.0
        assert profile['median_value'] == 250.0

    def test_profile_numeric_stats_id(self):
        import pandas as pd

        from data_hygiene_auditor.core import _compute_profile
        series = pd.Series(["1", "2", "3", "4", "5"])
        profile = _compute_profile(series, "id")
        assert profile['min_value'] == 1.0
        assert profile['max_value'] == 5.0
        assert profile['mean_value'] == 3.0

    def test_profile_empty_series(self):
        import pandas as pd

        from data_hygiene_auditor.core import _compute_profile
        series = pd.Series([None, None, ""])
        profile = _compute_profile(series, "freetext")
        assert profile['cardinality'] == 0
        assert profile['uniqueness_pct'] == 0.0
        assert profile['min_length'] == 0


class TestIssueHeadline:
    def test_mixed_format_label_and_detail(self):
        label, detail = issue_headline('mixed_format', {
            'field_type': 'date', 'dominant_format': 'YYYY-MM-DD',
            'dominant_count': 8, 'inconsistent_count': 2,
        })
        assert label == 'Mixed date formats'
        assert detail == '2 of 10 values deviate from YYYY-MM-DD'

    def test_custom_rule_uses_rule_name(self):
        label, detail = issue_headline(
            'custom_rule', {'message': 'too short'},
            {'rule_name': 'No short names'},
        )
        assert label == 'No short names'
        assert detail == 'too short'

    def test_describe_issue_composes_label_and_detail(self):
        # describe_issue (used by Excel + the API) is now derived from the
        # same headline producer as the HTML/PDF renderers.
        assert describe_issue('null_analysis', {
            'total_missing': 3, 'total_rows': 10, 'missing_pct': 30.0,
        }) == 'High missing rate: 3 of 10 values missing (30.0%)'

    def test_unknown_type_has_empty_detail(self):
        assert issue_headline('mystery', {}) == ('mystery', '')


class TestScoreBands:
    def test_band_boundaries(self):
        assert score_band(100) == 'clean'
        assert score_band(90) == 'clean'
        assert score_band(89) == 'attention'
        assert score_band(70) == 'attention'
        assert score_band(69) == 'significant'
        assert score_band(40) == 'significant'
        assert score_band(39) == 'critical'
        assert score_band(0) == 'critical'

    def test_label_matches_band(self):
        assert score_label(95) == 'Clean'
        assert score_label(75) == 'Needs Attention'
        assert score_label(50) == 'Significant Issues'
        assert score_label(10) == 'Critical'


class TestCombineOverallScore:
    def test_score_is_row_weighted_not_simple_mean(self):
        # 10 rows @ 90 and 90 rows @ 40 -> weighted 45, not the simple mean 65.
        big = {'overall_score': 40, 'sheets': {'s': {'row_count': 90}}}
        small = {'overall_score': 90, 'sheets': {'s': {'row_count': 10}}}
        assert combine_overall_score([small, big]) == 45

    def test_all_empty_files_fall_back_to_100(self):
        empty = {'overall_score': 100, 'sheets': {}}
        assert combine_overall_score([empty, empty]) == 100

    def test_single_file_equals_its_own_score(self):
        one = {'overall_score': 73, 'sheets': {'s': {'row_count': 5}}}
        assert combine_overall_score([one]) == 73


class TestMultiAudit:
    def _write_csv(self, path, rows):
        path.write_text("Name,Email\n" + "\n".join(rows) + "\n")

    def test_multi_audit_structure_and_shared_scoring(self, tmp_path):
        clean = tmp_path / "clean.csv"
        self._write_csv(clean, [f"User{i},user{i}@test.com" for i in range(8)])
        messy = tmp_path / "messy.csv"
        self._write_csv(messy, ["Test,N/A", "Test,N/A", "Test,N/A", "TBD,"])

        result = run_multi_audit([str(clean), str(messy)])
        assert result['total_files'] == 2
        assert set(result['files']) == {"clean.csv", "messy.csv"}
        assert result['total_rows'] == 12
        # The combined score must equal the shared helper over the per-file
        # results — one definition, no drift between entry points.
        expected = combine_overall_score(list(result['files'].values()))
        assert result['overall_score'] == expected
