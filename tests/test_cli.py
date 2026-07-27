"""Tests for the CLI: input resolution, SARIF, remediation CSV, and main()."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

from audit import run_audit
from data_hygiene_auditor.cli import (
    _export_remediation_csv,
    _generate_sarif,
    _resolve_inputs,
    main,
)

SAMPLE = Path(__file__).parent.parent / "samples" / "input" / "sample_messy_data.xlsx"


class TestResolveInputs:
    def test_single_supported_file(self):
        assert _resolve_inputs(str(SAMPLE)) == [str(SAMPLE)]

    def test_unsupported_extension_returns_empty(self, tmp_path):
        p = tmp_path / "notes.txt"
        p.write_text("hello")
        assert _resolve_inputs(str(p)) == []

    def test_directory_recurses_and_filters(self, tmp_path):
        (tmp_path / "a.csv").write_text("Name\nAlice\n")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.csv").write_text("Name\nBob\n")
        (tmp_path / "ignore.txt").write_text("x")
        found = _resolve_inputs(str(tmp_path))
        assert len(found) == 2
        assert all(f.lower().endswith(".csv") for f in found)

    def test_glob_pattern(self, tmp_path):
        (tmp_path / "x1.csv").write_text("Name\nA\n")
        (tmp_path / "x2.csv").write_text("Name\nB\n")
        found = _resolve_inputs(str(tmp_path / "*.csv"))
        assert len(found) == 2


class TestSarif:
    def test_structure_and_level_mapping(self):
        results = run_audit(str(SAMPLE))
        sarif = _generate_sarif([results], [str(SAMPLE)])
        assert sarif["version"] == "2.1.0"
        driver = sarif["runs"][0]["tool"]["driver"]
        assert driver["name"] == "data-hygiene-auditor"
        run_results = sarif["runs"][0]["results"]
        assert len(run_results) > 0
        assert {r["level"] for r in run_results} <= {"error", "warning", "note"}

    def test_custom_rule_id_prefix(self, tmp_path):
        rules = tmp_path / "rules.json"
        rules.write_text(json.dumps({"rules": [{
            "name": "No short names",
            "description": "d",
            "severity": "High",
            "condition": "min_length",
            "threshold": 10,
            "column_pattern": "name",
        }]}))
        results = run_audit(str(SAMPLE), rules_path=str(rules))
        sarif = _generate_sarif([results], [str(SAMPLE)])
        rule_ids = {r["ruleId"] for r in sarif["runs"][0]["results"]}
        assert any(rid.startswith("custom/") for rid in rule_ids)


class TestRemediationCsv:
    def test_rows_present_and_sorted_by_severity(self, tmp_path):
        results = run_audit(str(SAMPLE))
        out = tmp_path / "fixes.csv"
        _export_remediation_csv([results], str(out))
        with open(out, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0
        assert {"File", "Sheet", "Field", "Issue Type", "Severity"}.issubset(
            rows[0].keys()
        )
        order = {"High": 0, "Medium": 1, "Low": 2}
        ranks = [order.get(r["Severity"], 3) for r in rows]
        assert ranks == sorted(ranks)


class TestMain:
    def _argv(self, monkeypatch, argv):
        monkeypatch.setattr(sys, "argv", ["data-hygiene-audit", *argv])

    def test_generates_three_reports(self, tmp_path, monkeypatch):
        self._argv(monkeypatch, ["--input", str(SAMPLE), "--output", str(tmp_path), "--quiet"])
        main()
        stem = SAMPLE.stem
        assert (tmp_path / f"{stem}_audit_report.html").exists()
        assert (tmp_path / f"{stem}_audit_findings.xlsx").exists()
        assert (tmp_path / f"{stem}_audit_report.pdf").exists()

    def test_json_sarif_and_fixes_outputs(self, tmp_path, monkeypatch):
        sarif = tmp_path / "out.sarif"
        fixes = tmp_path / "fixes.csv"
        self._argv(monkeypatch, [
            "--input", str(SAMPLE), "--output", str(tmp_path), "--quiet",
            "--json", "--sarif", str(sarif), "--export-fixes", str(fixes),
        ])
        main()
        assert json.loads(sarif.read_text())["version"] == "2.1.0"
        assert fixes.exists()
        assert (tmp_path / f"{SAMPLE.stem}_audit_results.json").exists()

    def test_fail_under_exits_nonzero(self, tmp_path, monkeypatch):
        # The messy sample scores well under 100, so --fail-under 100 must fail.
        self._argv(monkeypatch, [
            "--input", str(SAMPLE), "--output", str(tmp_path),
            "--quiet", "--fail-under", "100",
        ])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_no_supported_files_exits(self, tmp_path, monkeypatch):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        self._argv(monkeypatch, ["--input", str(empty_dir), "--output", str(tmp_path), "--quiet"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
