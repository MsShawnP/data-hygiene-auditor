"""Public Python API for programmatic use.

Usage::

    from data_hygiene_auditor import audit_file

    result = audit_file("customers.xlsx")
    print(result.overall_score)
    for sheet in result.sheets:
        print(f"{sheet.name}: {sheet.health_score}/100")
        for finding in sheet.findings:
            print(f"  [{finding.severity}] {finding.field}: {finding.description}")
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import run_audit
from .reporting import generate_excel, generate_html, generate_pdf


@dataclass
class FixSuggestion:
    """An actionable fix suggestion with code snippet."""

    strategy: str
    description: str
    code: str


@dataclass
class Finding:
    """A single data quality issue found in a field."""

    field: str
    issue_type: str
    severity: str
    description: str
    why: str
    detail: Dict[str, Any] = field(default_factory=dict)
    fix: Optional[FixSuggestion] = None

    @property
    def is_high(self) -> bool:
        return self.severity == 'High'

    @property
    def is_medium(self) -> bool:
        return self.severity == 'Medium'

    @property
    def is_low(self) -> bool:
        return self.severity == 'Low'


@dataclass
class Duplicate:
    """A duplicate or phantom duplicate group."""

    duplicate_type: str
    severity: str
    rows: List[int]
    group_size: int
    why: str
    sample_data: List[Dict[str, str]] = field(default_factory=list)
    fix: Optional[FixSuggestion] = None


@dataclass
class FuzzyDuplicate:
    """A fuzzy duplicate group found via fingerprinting or Levenshtein."""

    match_method: str
    severity: str
    rows: List[int]
    group_size: int
    why: str
    field_differences: Dict[str, Any] = field(default_factory=dict)
    sample_data: List[Dict[str, str]] = field(default_factory=list)
    similarity_threshold: Optional[float] = None
    fix: Optional[FixSuggestion] = None


@dataclass
class FieldResult:
    """Audit results for a single field/column."""

    name: str
    inferred_type: str
    null_count: int
    blank_count: int
    whitespace_only: int
    total_missing: int
    missing_pct: float
    total_rows: int
    findings: List[Finding] = field(default_factory=list)


@dataclass
class SheetResult:
    """Audit results for a single sheet."""

    name: str
    row_count: int
    col_count: int
    health_score: int
    fields: List[FieldResult] = field(default_factory=list)
    duplicates: List[Duplicate] = field(default_factory=list)
    fuzzy_duplicates: List[FuzzyDuplicate] = field(default_factory=list)

    @property
    def findings(self) -> List[Finding]:
        """All findings across all fields in this sheet."""
        result = []
        for f in self.fields:
            result.extend(f.findings)
        return result

    @property
    def total_issues(self) -> int:
        return (
            len(self.findings)
            + len(self.duplicates)
            + len(self.fuzzy_duplicates)
        )


@dataclass
class AuditResult:
    """Complete audit result with typed access to all findings."""

    input_file: str
    audit_timestamp: str
    overall_score: int
    sheets: List[SheetResult] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return sum(s.total_issues for s in self.sheets)

    @property
    def findings(self) -> List[Finding]:
        """All findings across all sheets."""
        result = []
        for s in self.sheets:
            result.extend(s.findings)
        return result

    @property
    def high_issues(self) -> List[Finding]:
        return [f for f in self.findings if f.is_high]

    @property
    def medium_issues(self) -> List[Finding]:
        return [f for f in self.findings if f.is_medium]

    @property
    def low_issues(self) -> List[Finding]:
        return [f for f in self.findings if f.is_low]

    def to_dict(self) -> Dict[str, Any]:
        """Return the raw audit results dict."""
        return self._raw

    def generate_html(
        self, output_path: Optional[str] = None,
    ) -> str:
        """Generate HTML report. Returns the output path."""
        if output_path is None:
            output_path = os.path.join(
                tempfile.mkdtemp(),
                f"{Path(self.input_file).stem}_audit_report.html",
            )
        return generate_html(self._raw, output_path)

    def generate_excel(
        self, output_path: Optional[str] = None,
    ) -> str:
        """Generate Excel findings report. Returns the output path."""
        if output_path is None:
            output_path = os.path.join(
                tempfile.mkdtemp(),
                f"{Path(self.input_file).stem}_audit_findings.xlsx",
            )
        return generate_excel(self._raw, output_path)

    def generate_pdf(
        self, output_path: Optional[str] = None,
    ) -> str:
        """Generate PDF report. Returns the output path."""
        if output_path is None:
            output_path = os.path.join(
                tempfile.mkdtemp(),
                f"{Path(self.input_file).stem}_audit_report.pdf",
            )
        return generate_pdf(self._raw, output_path)


def _describe_issue(issue_type: str, detail: dict) -> str:
    """Generate a human-readable description for an issue."""
    if issue_type == 'mixed_format':
        return (
            f"Mixed {detail.get('field_type', '')} formats:"
            f" {detail.get('inconsistent_count', 0)} values"
            f" deviate from {detail.get('dominant_format', '')}"
        )
    if issue_type == 'wrong_purpose':
        return detail.get('issue', 'Wrong purpose')
    if issue_type in ('placeholder_value', 'placeholder'):
        return (
            f"Placeholder \"{detail.get('value', '')}\" found"
            f" {detail.get('count', 0)} times"
        )
    if issue_type == 'suspicious_repetition':
        return (
            f"\"{detail.get('value', '')}\" repeated"
            f" {detail.get('count', 0)} times"
        )
    if issue_type == 'null_analysis':
        return (
            f"{detail.get('total_missing', 0)} of"
            f" {detail.get('total_rows', 0)} values missing"
            f" ({detail.get('missing_pct', 0)}%)"
        )
    return str(issue_type)


def audit_file(path: str, fuzzy_threshold: float = 0.85) -> AuditResult:
    """Audit an Excel or CSV file and return typed results.

    Args:
        path: Path to an .xlsx, .xls, .csv, or .tsv file.
        fuzzy_threshold: Similarity threshold (0.0-1.0) for
            Levenshtein fuzzy duplicate matching. Default 0.85.

    Returns:
        AuditResult with typed access to all findings, scores,
        and report generation methods.
    """
    raw = run_audit(path, fuzzy_threshold=fuzzy_threshold)

    sheets = []
    for sheet_name, sheet_data in raw['sheets'].items():
        fields = []
        for col_name, field_data in sheet_data['fields'].items():
            null = field_data['null_analysis']
            findings = []
            for issue in field_data['issues']:
                raw_fix = issue.get('fix')
                fix_obj = None
                if raw_fix:
                    fix_obj = FixSuggestion(
                        strategy=raw_fix['strategy'],
                        description=raw_fix['description'],
                        code=raw_fix['code'],
                    )
                findings.append(Finding(
                    field=col_name,
                    issue_type=issue['type'],
                    severity=issue['severity'],
                    description=_describe_issue(
                        issue['type'], issue['detail'],
                    ),
                    why=issue.get('why', ''),
                    detail=issue['detail'],
                    fix=fix_obj,
                ))
            fields.append(FieldResult(
                name=col_name,
                inferred_type=field_data['inferred_type'],
                null_count=null['null_count'],
                blank_count=null['blank_count'],
                whitespace_only=null['whitespace_only'],
                total_missing=null['total_missing'],
                missing_pct=null['missing_pct'],
                total_rows=null['total_rows'],
                findings=findings,
            ))

        duplicates = []
        for dup in sheet_data['phantom_duplicates']:
            raw_fix = dup.get('fix')
            fix_obj = None
            if raw_fix:
                fix_obj = FixSuggestion(
                    strategy=raw_fix['strategy'],
                    description=raw_fix['description'],
                    code=raw_fix['code'],
                )
            duplicates.append(Duplicate(
                duplicate_type=dup['type'],
                severity=dup['severity'],
                rows=dup['rows'],
                group_size=dup['group_size'],
                why=dup.get('why', ''),
                sample_data=dup.get('sample_data', []),
                fix=fix_obj,
            ))

        fuzzy_dups = []
        for fuzz in sheet_data.get('fuzzy_duplicates', []):
            raw_fix = fuzz.get('fix')
            fix_obj = None
            if raw_fix:
                fix_obj = FixSuggestion(
                    strategy=raw_fix['strategy'],
                    description=raw_fix['description'],
                    code=raw_fix['code'],
                )
            fuzzy_dups.append(FuzzyDuplicate(
                match_method=fuzz['match_method'],
                severity=fuzz['severity'],
                rows=fuzz['rows'],
                group_size=fuzz['group_size'],
                why=fuzz.get('why', ''),
                field_differences=fuzz.get('field_differences', {}),
                sample_data=fuzz.get('sample_data', []),
                similarity_threshold=fuzz.get('similarity_threshold'),
                fix=fix_obj,
            ))

        sheets.append(SheetResult(
            name=sheet_name,
            row_count=sheet_data['row_count'],
            col_count=sheet_data['col_count'],
            health_score=sheet_data['health_score'],
            fields=fields,
            duplicates=duplicates,
            fuzzy_duplicates=fuzzy_dups,
        ))

    result = AuditResult(
        input_file=raw['input_file'],
        audit_timestamp=raw['audit_timestamp'],
        overall_score=raw['overall_score'],
        sheets=sheets,
    )
    result._raw = raw
    return result
