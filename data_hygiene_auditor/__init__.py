"""Data Hygiene Auditor — Detect data quality issues in Excel and CSV files."""

from .api import (
    AuditResult,
    Duplicate,
    FieldResult,
    Finding,
    FixSuggestion,
    FuzzyDuplicate,
    SchemaViolation,
    SheetResult,
    TrendData,
    audit_file,
)
from .core import SUPPORTED_EXTENSIONS, WHY_IT_MATTERS, _load_sheets, count_issues, run_audit  # noqa: F401
from .detection import (
    analyze_fuzzy_duplicates,
    analyze_mixed_formats,
    analyze_nulls,
    analyze_phantom_duplicates,
    analyze_placeholders,
    analyze_wrong_purpose,
    infer_field_type,
    rate_severity,
)
from .reporting import generate_excel, generate_html, generate_pdf
from .rules import Rule, evaluate_rule, load_rules
from .schema import generate_schema, load_schema, validate_schema
from .trend import compute_trend, load_baseline

__all__ = [
    'audit_file',
    'AuditResult',
    'Finding',
    'FixSuggestion',
    'Duplicate',
    'FuzzyDuplicate',
    'FieldResult',
    'SchemaViolation',
    'SheetResult',
    'TrendData',
    'run_audit',
    'count_issues',
    'SUPPORTED_EXTENSIONS',
    'WHY_IT_MATTERS',
    'infer_field_type',
    'analyze_nulls',
    'analyze_mixed_formats',
    'analyze_wrong_purpose',
    'analyze_placeholders',
    'analyze_fuzzy_duplicates',
    'analyze_phantom_duplicates',
    'rate_severity',
    'generate_html',
    'generate_excel',
    'generate_pdf',
    'load_schema',
    'generate_schema',
    'validate_schema',
    'load_baseline',
    'compute_trend',
    'load_rules',
    'evaluate_rule',
    'Rule',
]
