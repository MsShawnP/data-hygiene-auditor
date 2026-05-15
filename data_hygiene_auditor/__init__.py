"""Data Hygiene Auditor — Detect data quality issues in Excel and CSV files."""

from .core import SUPPORTED_EXTENSIONS, WHY_IT_MATTERS, _load_sheets, run_audit
from .detection import (
    analyze_mixed_formats,
    analyze_nulls,
    analyze_phantom_duplicates,
    analyze_placeholders,
    analyze_wrong_purpose,
    infer_field_type,
    rate_severity,
)
from .reporting import generate_excel, generate_html, generate_pdf

__all__ = [
    'run_audit',
    '_load_sheets',
    'SUPPORTED_EXTENSIONS',
    'WHY_IT_MATTERS',
    'infer_field_type',
    'analyze_nulls',
    'analyze_mixed_formats',
    'analyze_wrong_purpose',
    'analyze_placeholders',
    'analyze_phantom_duplicates',
    'rate_severity',
    'generate_html',
    'generate_excel',
    'generate_pdf',
]
