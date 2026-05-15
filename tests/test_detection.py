"""Tests for detection engines: field type inference, nulls, mixed formats."""
import pandas as pd

from audit import (
    analyze_mixed_formats,
    analyze_nulls,
    infer_field_type,
)


class TestInferFieldType:
    def test_date_by_name(self):
        assert infer_field_type("JoinDate", ["2023-01-01"]) == "date"
        assert infer_field_type("created_at", ["2023-01-01"]) == "date"
        assert infer_field_type("ship_date", ["anything"]) == "date"
        assert infer_field_type("dob", ["1990-01-01"]) == "date"

    def test_phone_by_name(self):
        assert infer_field_type("Phone", ["555-1234"]) == "phone"
        assert infer_field_type("mobile_number", ["555"]) == "phone"
        assert infer_field_type("Fax", ["555"]) == "phone"

    def test_email_by_name(self):
        assert infer_field_type("Email", ["a@b.com"]) == "email"
        assert infer_field_type("email_address", ["x"]) == "email"

    def test_currency_by_name(self):
        assert infer_field_type("Price", ["100"]) == "currency"
        assert infer_field_type("AccountBalance", ["$50"]) == "currency"
        assert infer_field_type("total_cost", ["10"]) == "currency"

    def test_id_by_name(self):
        assert infer_field_type("CustomerID", ["CUST-001"]) == "id"
        assert infer_field_type("sku_code", ["ABC"]) == "id"
        assert infer_field_type("ref_number", ["123"]) == "id"

    def test_phone_number_not_id(self):
        assert infer_field_type("phone_number", ["555"]) == "phone"

    def test_name_by_name(self):
        assert infer_field_type("FirstName", ["Alice"]) == "name"
        assert infer_field_type("last_name", ["Smith"]) == "name"

    def test_categorical_by_name(self):
        assert infer_field_type("Status", ["Active"]) == "categorical"
        assert infer_field_type("category_type", ["A"]) == "categorical"

    def test_freetext_by_name(self):
        assert infer_field_type("Notes", ["some text"]) == "freetext"
        assert infer_field_type("description", ["blah"]) == "freetext"

    def test_zipcode_by_name(self):
        assert infer_field_type("ZipCode", ["30301"]) == "zipcode"
        assert infer_field_type("postal_code", ["12345"]) == "zipcode"

    def test_date_by_content(self):
        values = ["2023-01-01", "2023-02-15", "2023-03-20"]
        assert infer_field_type("col1", values) == "date"

    def test_phone_by_content(self):
        values = ["(555) 123-4567", "(555) 234-5678", "(555) 345-6789"]
        assert infer_field_type("col1", values) == "phone"

    def test_currency_by_content(self):
        values = ["$100.00", "$250.50", "$1,000.00"]
        assert infer_field_type("col1", values) == "currency"

    def test_email_by_content(self):
        values = ["a@b.com", "c@d.org", "e@f.net"]
        assert infer_field_type("col1", values) == "email"

    def test_empty_column(self):
        assert infer_field_type("col1", [None, None, None]) == "empty"
        assert infer_field_type("col1", ["", "  ", ""]) == "empty"

    def test_freetext_fallback(self):
        values = ["hello world", "foo bar baz", "random stuff"]
        assert infer_field_type("col1", values) == "freetext"


class TestAnalyzeNulls:
    def test_no_missing(self):
        series = pd.Series(["a", "b", "c"])
        result = analyze_nulls(series)
        assert result["null_count"] == 0
        assert result["blank_count"] == 0
        assert result["whitespace_only"] == 0
        assert result["total_missing"] == 0
        assert result["missing_pct"] == 0.0

    def test_null_values(self):
        series = pd.Series(["a", None, "c", None])
        result = analyze_nulls(series)
        assert result["null_count"] == 2
        assert result["total_missing"] == 2
        assert result["missing_pct"] == 50.0

    def test_blank_strings(self):
        series = pd.Series(["a", "", "c"])
        result = analyze_nulls(series)
        assert result["blank_count"] == 1
        assert result["whitespace_only"] == 0
        assert result["total_missing"] == 1

    def test_whitespace_only(self):
        series = pd.Series(["a", "  ", "\t", "b"])
        result = analyze_nulls(series)
        assert result["whitespace_only"] == 2
        assert result["blank_count"] == 0
        assert result["total_missing"] == 2

    def test_blank_and_whitespace_disjoint(self):
        series = pd.Series(["a", "", "  ", None, "b"])
        result = analyze_nulls(series)
        assert result["null_count"] == 1
        assert result["blank_count"] == 1
        assert result["whitespace_only"] == 1
        assert result["total_missing"] == 3

    def test_empty_series(self):
        series = pd.Series([], dtype=object)
        result = analyze_nulls(series)
        assert result["total_rows"] == 0
        assert result["missing_pct"] == 0


class TestAnalyzeMixedFormats:
    def test_consistent_dates(self):
        series = pd.Series(["2023-01-01", "2023-02-15", "2023-03-20"])
        result = analyze_mixed_formats(series, "date")
        assert result is None

    def test_mixed_dates(self):
        series = pd.Series(["2023-01-01", "01/15/2023", "Jan 20, 2023"])
        result = analyze_mixed_formats(series, "date")
        assert result is not None
        assert result["inconsistent_count"] == 2
        assert result["dominant_format"] == "YYYY-MM-DD"

    def test_mixed_phones(self):
        series = pd.Series(["(555) 123-4567", "555-234-5678", "5551234567"])
        result = analyze_mixed_formats(series, "phone")
        assert result is not None
        assert len(result["format_distribution"]) == 3

    def test_mixed_currency(self):
        series = pd.Series(["$100.00", "200.00", "$300"])
        result = analyze_mixed_formats(series, "currency")
        assert result is not None
        assert result["inconsistent_count"] >= 1

    def test_non_format_type_returns_none(self):
        series = pd.Series(["Alice", "Bob", "Charlie"])
        assert analyze_mixed_formats(series, "name") is None
        assert analyze_mixed_formats(series, "freetext") is None

    def test_all_null_returns_none(self):
        series = pd.Series([None, None, None])
        assert analyze_mixed_formats(series, "date") is None

    def test_nonstandard_samples_captured(self):
        series = pd.Series(["2023-01-01", "2023-02-15", "not-a-date"])
        result = analyze_mixed_formats(series, "date")
        assert result is not None
        assert "not-a-date" in result["sample_nonstandard"]
