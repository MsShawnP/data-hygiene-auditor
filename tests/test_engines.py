"""Tests for remaining engines: wrong purpose, placeholders, phantom duplicates."""
import pandas as pd

from audit import (
    analyze_phantom_duplicates,
    analyze_placeholders,
    analyze_wrong_purpose,
    rate_severity,
)


class TestAnalyzeWrongPurpose:
    def test_code_in_name_field(self):
        series = pd.Series(["Alice", "REF-4421", "Charlie"])
        findings = analyze_wrong_purpose(series, "FirstName", "name")
        assert any(f["issue"] == "Code/ID stuffed in name field" for f in findings)

    def test_numeric_in_name_field(self):
        series = pd.Series(["Alice", "12345", "Charlie"])
        findings = analyze_wrong_purpose(series, "FirstName", "name")
        assert any(f["issue"] == "Numeric value in name field" for f in findings)

    def test_text_in_currency_field(self):
        series = pd.Series(["$100.00", "five thousand", "$300.00"])
        findings = analyze_wrong_purpose(series, "Amount", "currency")
        assert any(f["issue"] == "Text in currency field" for f in findings)

    def test_invalid_email(self):
        series = pd.Series(["alice@example.com", "not-an-email", "bob@test.com"])
        findings = analyze_wrong_purpose(series, "Email", "email")
        assert any(f["issue"] == "Invalid email format" for f in findings)

    def test_mixed_id_formats(self):
        series = pd.Series(["CUST-001", "CUST-002", "1003", "1004"])
        findings = analyze_wrong_purpose(series, "CustomerID", "id")
        assert any(f["issue"] == "Mixed ID formats" for f in findings)

    def test_mixed_boolean_representations(self):
        series = pd.Series(["Y", "N", "1", "0"])
        findings = analyze_wrong_purpose(series, "Status", "categorical")
        assert any(f["issue"] == "Mixed boolean representations" for f in findings)

    def test_inconsistent_casing(self):
        series = pd.Series(["Active", "active", "ACTIVE"])
        findings = analyze_wrong_purpose(series, "Status", "categorical")
        assert any("Inconsistent casing" in f["issue"] for f in findings)

    def test_clean_name_field(self):
        series = pd.Series(["Alice", "Bob", "Charlie"])
        findings = analyze_wrong_purpose(series, "FirstName", "name")
        assert findings == []

    def test_empty_series(self):
        series = pd.Series([None, None])
        findings = analyze_wrong_purpose(series, "col", "name")
        assert findings == []


class TestAnalyzePlaceholders:
    def test_detects_test_values(self):
        series = pd.Series(["Alice", "Test", "Charlie", "Test"])
        findings = analyze_placeholders(series, "Name")
        placeholder_vals = [f["value"] for f in findings if f["type"] == "placeholder_value"]
        assert "Test" in placeholder_vals

    def test_detects_na(self):
        series = pd.Series(["Alice", "N/A", "Charlie"])
        findings = analyze_placeholders(series, "Name")
        placeholder_vals = [f["value"] for f in findings if f["type"] == "placeholder_value"]
        assert "N/A" in placeholder_vals

    def test_detects_tbd(self):
        series = pd.Series(["TBD", "Alice", "TBD"])
        findings = analyze_placeholders(series, "Name")
        placeholder_vals = [f["value"] for f in findings if f["type"] == "placeholder_value"]
        assert "TBD" in placeholder_vals

    def test_detects_suspicious_repetition(self):
        series = pd.Series(["(555) 123-4567"] * 5 + ["(555) 999-0000"] * 2)
        findings = analyze_placeholders(series, "Phone")
        repetition_vals = [f["value"] for f in findings if f["type"] == "suspicious_repetition"]
        assert "(555) 123-4567" in repetition_vals

    def test_no_findings_on_clean_data(self):
        series = pd.Series(["Alice", "Bob", "Charlie", "Diana", "Edward"])
        findings = analyze_placeholders(series, "Name")
        assert findings == []

    def test_all_null_no_findings(self):
        series = pd.Series([None, None, None])
        findings = analyze_placeholders(series, "Name")
        assert findings == []


class TestAnalyzePhantomDuplicates:
    def test_exact_duplicates(self):
        df = pd.DataFrame({
            "ID": ["1", "2", "3"],
            "Name": ["Alice", "Alice", "Bob"],
            "Email": ["a@b.com", "a@b.com", "b@c.com"],
        })
        findings = analyze_phantom_duplicates(df, "Sheet1")
        assert len(findings) == 1
        assert findings[0]["type"] == "exact_duplicate"

    def test_phantom_duplicates_case_diff(self):
        df = pd.DataFrame({
            "ID": ["1", "2", "3"],
            "Name": ["Alice", "alice", "Bob"],
            "Email": ["a@b.com", "A@B.COM", "b@c.com"],
        })
        findings = analyze_phantom_duplicates(df, "Sheet1")
        assert len(findings) == 1
        assert findings[0]["type"] == "phantom_duplicate"

    def test_phantom_duplicates_whitespace_diff(self):
        df = pd.DataFrame({
            "ID": ["1", "2", "3"],
            "Name": ["Alice", " Alice ", "Bob"],
            "Email": ["a@b.com", "a@b.com", "b@c.com"],
        })
        findings = analyze_phantom_duplicates(df, "Sheet1")
        assert len(findings) == 1

    def test_no_duplicates(self):
        df = pd.DataFrame({
            "ID": ["1", "2", "3"],
            "Name": ["Alice", "Bob", "Charlie"],
            "Email": ["a@b.com", "b@c.com", "c@d.com"],
        })
        findings = analyze_phantom_duplicates(df, "Sheet1")
        assert findings == []

    def test_id_columns_excluded_from_matching(self):
        df = pd.DataFrame({
            "CustomerID": ["CUST-001", "CUST-002"],
            "Name": ["Alice", "Alice"],
            "Email": ["a@b.com", "a@b.com"],
        })
        findings = analyze_phantom_duplicates(df, "Sheet1")
        assert len(findings) == 1

    def test_empty_dataframe(self):
        df = pd.DataFrame({"A": [], "B": []})
        findings = analyze_phantom_duplicates(df, "Sheet1")
        assert findings == []

    def test_single_row(self):
        df = pd.DataFrame({"Name": ["Alice"], "Email": ["a@b.com"]})
        findings = analyze_phantom_duplicates(df, "Sheet1")
        assert findings == []


class TestRateSeverity:
    def test_high_mixed_format(self):
        assert rate_severity("mixed_format", {"inconsistent_pct": 50}) == "High"

    def test_medium_mixed_format(self):
        assert rate_severity("mixed_format", {"inconsistent_pct": 20}) == "Medium"

    def test_low_mixed_format(self):
        assert rate_severity("mixed_format", {"inconsistent_pct": 5}) == "Low"

    def test_wrong_purpose_always_high(self):
        assert rate_severity("wrong_purpose", {}) == "High"

    def test_exact_duplicate_always_high(self):
        assert rate_severity("phantom_duplicate", {"type": "exact_duplicate"}) == "High"

    def test_null_no_severity_when_low(self):
        assert rate_severity("null_analysis", {"missing_pct": 3}) is None

    def test_null_high_severity(self):
        assert rate_severity("null_analysis", {"missing_pct": 60}) == "High"
