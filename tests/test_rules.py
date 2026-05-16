"""Tests for custom rule engine — loader and evaluator."""

import json

import pandas as pd
import pytest

from data_hygiene_auditor.rules import Rule, evaluate_rule, load_rules


@pytest.fixture
def tmp_rules_file(tmp_path):
    """Helper to write a rules JSON file and return its path."""
    def _write(data):
        path = tmp_path / "rules.json"
        path.write_text(json.dumps(data))
        return str(path)
    return _write


class TestLoadRules:

    def test_loads_valid_rules(self, tmp_rules_file):
        path = tmp_rules_file({
            "rules": [
                {
                    "name": "Phone format",
                    "description": "Must match US format",
                    "severity": "High",
                    "condition": "regex_match",
                    "threshold": r"^\(\d{3}\) \d{3}-\d{4}$",
                    "column_pattern": "phone",
                }
            ]
        })
        rules = load_rules(path)
        assert len(rules) == 1
        assert rules[0].name == "Phone format"
        assert rules[0].severity == "High"
        assert rules[0].condition == "regex_match"

    def test_rejects_missing_rules_key(self, tmp_rules_file):
        path = tmp_rules_file({"checks": []})
        with pytest.raises(ValueError, match="top-level 'rules' array"):
            load_rules(path)

    def test_rejects_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json {{{")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_rules(str(path))

    def test_rejects_missing_required_fields(self, tmp_rules_file):
        path = tmp_rules_file({
            "rules": [{"name": "incomplete"}]
        })
        with pytest.raises(ValueError, match="missing required field"):
            load_rules(path)

    def test_rejects_invalid_condition(self, tmp_rules_file):
        path = tmp_rules_file({
            "rules": [{
                "name": "bad",
                "description": "x",
                "severity": "High",
                "condition": "magic_check",
                "threshold": 5,
            }]
        })
        with pytest.raises(ValueError, match="invalid condition"):
            load_rules(path)

    def test_rejects_invalid_severity(self, tmp_rules_file):
        path = tmp_rules_file({
            "rules": [{
                "name": "bad",
                "description": "x",
                "severity": "Critical",
                "condition": "min_length",
                "threshold": 5,
            }]
        })
        with pytest.raises(ValueError, match="severity must be"):
            load_rules(path)

    def test_rejects_invalid_regex(self, tmp_rules_file):
        path = tmp_rules_file({
            "rules": [{
                "name": "bad regex",
                "description": "x",
                "severity": "High",
                "condition": "regex_match",
                "threshold": "[invalid(",
            }]
        })
        with pytest.raises(ValueError, match="invalid regex"):
            load_rules(path)

    def test_rejects_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_rules("/nonexistent/rules.json")

    def test_loads_multiple_rules(self, tmp_rules_file):
        path = tmp_rules_file({
            "rules": [
                {
                    "name": "R1",
                    "description": "d1",
                    "severity": "Low",
                    "condition": "min_length",
                    "threshold": 3,
                },
                {
                    "name": "R2",
                    "description": "d2",
                    "severity": "Medium",
                    "condition": "max_missing_pct",
                    "threshold": 10,
                },
            ]
        })
        rules = load_rules(path)
        assert len(rules) == 2

    def test_column_pattern_default(self, tmp_rules_file):
        path = tmp_rules_file({
            "rules": [{
                "name": "R",
                "description": "d",
                "severity": "Low",
                "condition": "min_length",
                "threshold": 1,
            }]
        })
        rules = load_rules(path)
        assert rules[0].column_pattern == '*'

    def test_columns_list(self, tmp_rules_file):
        path = tmp_rules_file({
            "rules": [{
                "name": "R",
                "description": "d",
                "severity": "Low",
                "condition": "min_length",
                "threshold": 1,
                "columns": ["Name", "Email"],
            }]
        })
        rules = load_rules(path)
        assert rules[0].columns == ["Name", "Email"]


class TestRuleMatchesColumn:

    def test_wildcard_matches_all(self):
        rule = Rule("R", "d", "Low", "min_length", 1, column_pattern="*")
        assert rule.matches_column("anything")

    def test_pattern_matches(self):
        rule = Rule("R", "d", "Low", "min_length", 1, column_pattern="phone|tel")
        assert rule.matches_column("Phone")
        assert rule.matches_column("telephone")
        assert not rule.matches_column("email")

    def test_explicit_columns_list(self):
        rule = Rule("R", "d", "Low", "min_length", 1, columns=["Name", "Email"])
        assert rule.matches_column("Name")
        assert rule.matches_column("Email")
        assert not rule.matches_column("Phone")


class TestEvaluateRuleRegex:

    def test_regex_match_finds_violations(self):
        rule = Rule("R", "Must be digits", "High", "regex_match", r"^\d+$")
        series = pd.Series(["123", "456", "abc", "78x"])
        result = evaluate_rule(rule, series, "ID")
        assert result is not None
        assert result['detail']['violations'] == 2
        assert "abc" in result['detail']['examples']

    def test_regex_match_no_violations(self):
        rule = Rule("R", "d", "High", "regex_match", r"^\d+$")
        series = pd.Series(["123", "456", "789"])
        result = evaluate_rule(rule, series, "ID")
        assert result is None

    def test_not_regex_match_finds_violations(self):
        rule = Rule("R", "No SSNs", "High", "not_regex_match", r"^\d{3}-\d{2}-\d{4}$")
        series = pd.Series(["hello", "123-45-6789", "world"])
        result = evaluate_rule(rule, series, "Notes")
        assert result is not None
        assert result['detail']['violations'] == 1

    def test_not_regex_match_no_violations(self):
        rule = Rule("R", "d", "High", "not_regex_match", r"^\d{3}-\d{2}-\d{4}$")
        series = pd.Series(["hello", "world"])
        result = evaluate_rule(rule, series, "Notes")
        assert result is None


class TestEvaluateRuleLength:

    def test_min_length_finds_short_values(self):
        rule = Rule("R", "Too short", "Medium", "min_length", 5)
        series = pd.Series(["hello", "hi", "world", "yo"])
        result = evaluate_rule(rule, series, "Name")
        assert result is not None
        assert result['detail']['violations'] == 2

    def test_max_length_finds_long_values(self):
        rule = Rule("R", "Too long", "Low", "max_length", 5)
        series = pd.Series(["hi", "toolongvalue", "ok", "another_long"])
        result = evaluate_rule(rule, series, "Code")
        assert result is not None
        assert result['detail']['violations'] == 2

    def test_min_length_all_pass(self):
        rule = Rule("R", "d", "Low", "min_length", 2)
        series = pd.Series(["hello", "world", "ok"])
        result = evaluate_rule(rule, series, "Name")
        assert result is None


class TestEvaluateRuleValues:

    def test_allowed_values_finds_violations(self):
        rule = Rule("R", "Invalid status", "High", "allowed_values", ["active", "inactive", "pending"])
        series = pd.Series(["Active", "inactive", "UNKNOWN", "deleted"])
        result = evaluate_rule(rule, series, "Status")
        assert result is not None
        assert result['detail']['violations'] == 2

    def test_allowed_values_case_insensitive(self):
        rule = Rule("R", "d", "Low", "allowed_values", ["yes", "no"])
        series = pd.Series(["Yes", "NO", "yes"])
        result = evaluate_rule(rule, series, "Flag")
        assert result is None

    def test_disallowed_values_finds_matches(self):
        rule = Rule("R", "No test data", "Medium", "disallowed_values", ["test", "n/a", "tbd"])
        series = pd.Series(["John", "Test", "N/A", "Jane"])
        result = evaluate_rule(rule, series, "Name")
        assert result is not None
        assert result['detail']['violations'] == 2

    def test_disallowed_values_no_matches(self):
        rule = Rule("R", "d", "Low", "disallowed_values", ["test", "n/a"])
        series = pd.Series(["John", "Jane", "Bob"])
        result = evaluate_rule(rule, series, "Name")
        assert result is None


class TestEvaluateRuleMissing:

    def test_max_missing_pct_exceeds(self):
        rule = Rule("R", "Too many missing", "High", "max_missing_pct", 10)
        series = pd.Series(["a", None, None, "b", "", None])
        result = evaluate_rule(rule, series, "Field")
        assert result is not None
        assert result['detail']['actual'] > 10

    def test_max_missing_pct_within(self):
        rule = Rule("R", "d", "Low", "max_missing_pct", 50)
        series = pd.Series(["a", "b", "c", None])
        result = evaluate_rule(rule, series, "Field")
        assert result is None


class TestEvaluateRuleColumnFilter:

    def test_skips_non_matching_column(self):
        rule = Rule("R", "d", "High", "min_length", 5, column_pattern="phone")
        series = pd.Series(["hi"])
        result = evaluate_rule(rule, series, "Email")
        assert result is None

    def test_applies_to_matching_column(self):
        rule = Rule("R", "d", "High", "min_length", 5, column_pattern="phone")
        series = pd.Series(["hi"])
        result = evaluate_rule(rule, series, "Phone")
        assert result is not None

    def test_empty_series_returns_none(self):
        rule = Rule("R", "d", "High", "regex_match", r"\d+")
        series = pd.Series([None, None, ""])
        result = evaluate_rule(rule, series, "Col")
        assert result is None
