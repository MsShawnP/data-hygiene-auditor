"""Integration and edge case tests."""
import os
import tempfile
from pathlib import Path

from audit import _load_sheets, generate_excel, generate_html, generate_pdf, run_audit
from data_hygiene_auditor.core import count_issues

SAMPLE_PATH = Path(__file__).parent.parent / "samples" / "input" / "sample_messy_data.xlsx"


class TestIntegration:
    def test_full_audit_issue_counts(self):
        results = run_audit(str(SAMPLE_PATH))
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
            sheets = _load_sheets(f.name)
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

    def test_score_floors_at_zero(self):
        results = run_audit(str(SAMPLE_PATH))
        for sheet in results["sheets"].values():
            assert sheet["health_score"] >= 0


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

    def test_includes_fuzzy_duplicates(self):
        results = run_audit(str(SAMPLE_PATH))
        has_fuzzy = any(
            len(sheet.get("fuzzy_duplicates", [])) > 0
            for sheet in results["sheets"].values()
        )
        if has_fuzzy:
            counts = count_issues(results)
            no_fuzzy_total = 0
            for sheet in results["sheets"].values():
                for field in sheet["fields"].values():
                    no_fuzzy_total += len(field["issues"])
                no_fuzzy_total += len(sheet["phantom_duplicates"])
                no_fuzzy_total += len(sheet.get("schema_violations", []))
            assert counts['total'] > no_fuzzy_total

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
