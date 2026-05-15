"""Tests for the typed Python API (audit_file)."""
import os
import tempfile
from pathlib import Path

from audit import (
    AuditResult,
    Duplicate,
    FieldResult,
    Finding,
    SheetResult,
    audit_file,
)

SAMPLE_PATH = Path(__file__).parent.parent / "samples" / "input" / "sample_messy_data.xlsx"


class TestAuditFile:
    def test_returns_audit_result(self):
        result = audit_file(str(SAMPLE_PATH))
        assert isinstance(result, AuditResult)

    def test_has_sheets(self):
        result = audit_file(str(SAMPLE_PATH))
        assert len(result.sheets) == 2
        names = [s.name for s in result.sheets]
        assert "Customers" in names
        assert "Orders" in names

    def test_overall_score(self):
        result = audit_file(str(SAMPLE_PATH))
        assert isinstance(result.overall_score, int)
        assert 0 <= result.overall_score <= 100
        assert result.overall_score < 70

    def test_timestamp_and_file(self):
        result = audit_file(str(SAMPLE_PATH))
        assert result.input_file == "sample_messy_data.xlsx"
        assert result.audit_timestamp


class TestSheetResult:
    def test_sheet_fields(self):
        result = audit_file(str(SAMPLE_PATH))
        customers = [s for s in result.sheets if s.name == "Customers"][0]
        assert isinstance(customers, SheetResult)
        assert customers.row_count > 0
        assert customers.col_count > 0
        assert 0 <= customers.health_score <= 100
        assert len(customers.fields) > 0

    def test_field_result_types(self):
        result = audit_file(str(SAMPLE_PATH))
        customers = [s for s in result.sheets if s.name == "Customers"][0]
        for f in customers.fields:
            assert isinstance(f, FieldResult)
            assert f.name
            assert f.inferred_type
            assert f.total_rows > 0

    def test_findings_from_sheet(self):
        result = audit_file(str(SAMPLE_PATH))
        customers = [s for s in result.sheets if s.name == "Customers"][0]
        assert len(customers.findings) > 0
        for finding in customers.findings:
            assert isinstance(finding, Finding)
            assert finding.severity in ("High", "Medium", "Low")

    def test_duplicates(self):
        result = audit_file(str(SAMPLE_PATH))
        customers = [s for s in result.sheets if s.name == "Customers"][0]
        assert len(customers.duplicates) > 0
        for dup in customers.duplicates:
            assert isinstance(dup, Duplicate)
            assert dup.group_size >= 2
            assert len(dup.rows) >= 2

    def test_total_issues(self):
        result = audit_file(str(SAMPLE_PATH))
        for sheet in result.sheets:
            assert sheet.total_issues >= len(sheet.findings)


class TestFindingProperties:
    def test_severity_helpers(self):
        f = Finding(
            field="test", issue_type="test",
            severity="High", description="test", why="test",
        )
        assert f.is_high is True
        assert f.is_medium is False
        assert f.is_low is False

    def test_medium_severity(self):
        f = Finding(
            field="test", issue_type="test",
            severity="Medium", description="test", why="test",
        )
        assert f.is_high is False
        assert f.is_medium is True

    def test_low_severity(self):
        f = Finding(
            field="test", issue_type="test",
            severity="Low", description="test", why="test",
        )
        assert f.is_low is True


class TestAuditResultProperties:
    def test_total_issues(self):
        result = audit_file(str(SAMPLE_PATH))
        assert result.total_issues > 0
        manual_total = sum(s.total_issues for s in result.sheets)
        assert result.total_issues == manual_total

    def test_severity_filters(self):
        result = audit_file(str(SAMPLE_PATH))
        highs = result.high_issues
        mediums = result.medium_issues
        lows = result.low_issues
        assert len(highs) > 0
        assert all(f.is_high for f in highs)
        assert all(f.is_medium for f in mediums)
        assert all(f.is_low for f in lows)

    def test_to_dict(self):
        result = audit_file(str(SAMPLE_PATH))
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "sheets" in d
        assert "overall_score" in d


class TestReportGeneration:
    def test_generate_html(self):
        result = audit_file(str(SAMPLE_PATH))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = result.generate_html(
                os.path.join(tmpdir, "report.html"),
            )
            assert os.path.exists(path)
            content = Path(path).read_text(encoding="utf-8")
            assert "Data Hygiene Audit Report" in content

    def test_generate_html_default_path(self):
        result = audit_file(str(SAMPLE_PATH))
        path = result.generate_html()
        assert os.path.exists(path)
        assert path.endswith(".html")

    def test_generate_excel(self):
        result = audit_file(str(SAMPLE_PATH))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = result.generate_excel(
                os.path.join(tmpdir, "findings.xlsx"),
            )
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_generate_pdf(self):
        result = audit_file(str(SAMPLE_PATH))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = result.generate_pdf(
                os.path.join(tmpdir, "report.pdf"),
            )
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0


class TestCSVApi:
    def test_csv_audit(self):
        with tempfile.NamedTemporaryFile(
            suffix=".csv", mode="w", delete=False, newline="",
        ) as f:
            f.write("Name,Phone,JoinDate\n")
            f.write("Alice,(555) 123-4567,2023-01-15\n")
            f.write("Bob,555-234-5678,01/15/2023\n")
            f.write("Test,000-000-0000,N/A\n")
        try:
            result = audit_file(f.name)
            assert isinstance(result, AuditResult)
            assert len(result.sheets) == 1
            assert result.total_issues > 0
        finally:
            os.unlink(f.name)
