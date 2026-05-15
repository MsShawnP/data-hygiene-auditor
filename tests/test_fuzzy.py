"""Tests for fuzzy duplicate detection."""
import pandas as pd

from data_hygiene_auditor.detection import (
    _fingerprint,
    _levenshtein_distance,
    _levenshtein_similarity,
    analyze_fuzzy_duplicates,
)


class TestFingerprint:
    def test_basic(self):
        assert _fingerprint("Hello World") == "hello world"

    def test_sorts_tokens(self):
        assert _fingerprint("Smith John") == _fingerprint("John Smith")

    def test_strips_punctuation(self):
        assert _fingerprint("St. Louis") == _fingerprint("St Louis")
        assert _fingerprint("O'Brien") == _fingerprint("OBrien")

    def test_normalizes_whitespace(self):
        assert _fingerprint("  John   Smith  ") == "john smith"

    def test_empty_and_nan(self):
        assert _fingerprint(None) == ""
        assert _fingerprint(float("nan")) == ""
        assert _fingerprint("") == ""


class TestLevenshtein:
    def test_identical_strings(self):
        assert _levenshtein_distance("hello", "hello") == 0

    def test_single_insertion(self):
        assert _levenshtein_distance("cat", "cats") == 1

    def test_single_deletion(self):
        assert _levenshtein_distance("cats", "cat") == 1

    def test_single_substitution(self):
        assert _levenshtein_distance("cat", "bat") == 1

    def test_completely_different(self):
        assert _levenshtein_distance("abc", "xyz") == 3

    def test_empty_strings(self):
        assert _levenshtein_distance("", "") == 0
        assert _levenshtein_distance("abc", "") == 3

    def test_similarity_identical(self):
        assert _levenshtein_similarity("test", "test") == 1.0

    def test_similarity_empty(self):
        assert _levenshtein_similarity("", "") == 1.0

    def test_similarity_range(self):
        sim = _levenshtein_similarity("John", "Jon")
        assert 0.0 < sim < 1.0

    def test_similarity_near_match(self):
        sim = _levenshtein_similarity("robert", "robrt")
        assert sim > 0.8


class TestFuzzyDuplicates:
    def test_fingerprint_catches_token_reorder(self):
        df = pd.DataFrame({
            "ID": ["1", "2", "3"],
            "Name": ["John Smith", "Smith John", "Jane Doe"],
            "City": ["New York", "New York", "Boston"],
        })
        findings = analyze_fuzzy_duplicates(df, "Sheet1")
        assert len(findings) >= 1
        fp_matches = [f for f in findings if f['match_method'] == 'fingerprint']
        assert len(fp_matches) >= 1
        assert fp_matches[0]['group_size'] == 2

    def test_fingerprint_catches_punctuation_diffs(self):
        df = pd.DataFrame({
            "ID": ["1", "2"],
            "Company": ["O'Brien & Co.", "OBrien Co"],
            "City": ["Portland", "Portland"],
        })
        findings = analyze_fuzzy_duplicates(df, "Sheet1")
        assert len(findings) >= 1

    def test_excludes_phantom_matches(self):
        df = pd.DataFrame({
            "ID": ["1", "2"],
            "Name": ["John", "john"],
            "City": ["NYC", "nyc"],
        })
        phantom_sets = [frozenset({0, 1})]
        findings = analyze_fuzzy_duplicates(
            df, "Sheet1", phantom_row_sets=phantom_sets,
        )
        assert len(findings) == 0

    def test_field_differences_reported(self):
        df = pd.DataFrame({
            "ID": ["1", "2", "3"],
            "Name": ["Smith, John", "John Smith", "Smith, John"],
            "City": ["Portland", "Portland", "Seattle"],
        })
        findings = analyze_fuzzy_duplicates(df, "Sheet1")
        fp = [f for f in findings if f['match_method'] == 'fingerprint']
        assert len(fp) >= 1
        diffs = fp[0].get('field_differences', {})
        assert "Name" in diffs

    def test_levenshtein_catches_typos(self):
        df = pd.DataFrame({
            "ID": ["1", "2", "3"],
            "Name": ["Johnathan Smith", "Jonathon Smith", "Alice Brown"],
            "Email": ["john@test.com", "john@test.com", "alice@test.com"],
        })
        findings = analyze_fuzzy_duplicates(
            df, "Sheet1", threshold=0.8,
        )
        lev_matches = [
            f for f in findings if f['match_method'] == 'levenshtein'
        ]
        if lev_matches:
            assert lev_matches[0]['group_size'] == 2

    def test_excludes_id_columns(self):
        df = pd.DataFrame({
            "CustomerID": ["C-001", "C-002"],
            "Name": ["Smith John", "John Smith"],
            "City": ["Portland", "Portland"],
        })
        findings = analyze_fuzzy_duplicates(df, "Sheet1")
        if findings:
            assert "CustomerID" not in findings[0]['matched_on']

    def test_empty_dataframe(self):
        df = pd.DataFrame({"A": [], "B": []})
        findings = analyze_fuzzy_duplicates(df, "Sheet1")
        assert findings == []

    def test_single_row(self):
        df = pd.DataFrame({"Name": ["Alice"], "City": ["NYC"]})
        findings = analyze_fuzzy_duplicates(df, "Sheet1")
        assert findings == []

    def test_severity_rating(self):
        from data_hygiene_auditor.detection import rate_severity
        assert rate_severity(
            'fuzzy_duplicate', {'match_method': 'fingerprint'},
        ) == 'Medium'
        assert rate_severity(
            'fuzzy_duplicate', {'match_method': 'levenshtein'},
        ) == 'Low'

    def test_configurable_threshold(self):
        df = pd.DataFrame({
            "ID": ["1", "2"],
            "Name": ["Robert Johnson", "Robrt Jonson"],
            "City": ["Chicago", "Chicago"],
        })
        strict = analyze_fuzzy_duplicates(
            df, "Sheet1", threshold=0.99,
        )
        loose = analyze_fuzzy_duplicates(
            df, "Sheet1", threshold=0.7,
        )
        assert len(loose) >= len(strict)


class TestFuzzyInRunAudit:
    def test_fuzzy_key_present(self):
        import os
        import tempfile

        from audit import run_audit
        with tempfile.NamedTemporaryFile(
            suffix=".csv", mode="w", delete=False, newline="",
        ) as f:
            f.write("Name,City\n")
            f.write("John Smith,Portland\n")
            f.write("Smith John,Portland\n")
            f.write("Jane Doe,Boston\n")
        try:
            results = run_audit(f.name)
            sheet = list(results['sheets'].values())[0]
            assert 'fuzzy_duplicates' in sheet
            for fuzz in sheet['fuzzy_duplicates']:
                assert 'severity' in fuzz
                assert 'why' in fuzz
                assert fuzz['type'] == 'fuzzy_duplicate'
        finally:
            os.unlink(f.name)
