#!/usr/bin/env python3
"""Backward-compatible shim — delegates to data_hygiene_auditor package.

Keeps `python audit.py` and `from audit import ...` working while the real
code lives in data_hygiene_auditor/.
"""

from data_hygiene_auditor import (  # noqa: F401
    SUPPORTED_EXTENSIONS,
    WHY_IT_MATTERS,
    AuditResult,
    Duplicate,
    FieldResult,
    Finding,
    FuzzyDuplicate,
    SheetResult,
    _load_sheets,
    analyze_fuzzy_duplicates,
    analyze_mixed_formats,
    analyze_nulls,
    analyze_phantom_duplicates,
    analyze_placeholders,
    analyze_wrong_purpose,
    audit_file,
    generate_excel,
    generate_html,
    generate_pdf,
    infer_field_type,
    rate_severity,
    run_audit,
)
from data_hygiene_auditor.cli import main  # noqa: F401

if __name__ == '__main__':
    main()
