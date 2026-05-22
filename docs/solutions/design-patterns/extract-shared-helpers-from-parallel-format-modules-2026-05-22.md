---
title: Extract shared business logic from multi-format report generators
date: 2026-05-22
last_updated: 2026-05-22
category: design-patterns
module: data_hygiene_auditor.reporting
problem_type: design_pattern
component: tooling
severity: medium
applies_when:
  - "Multiple format-specific modules (HTML, PDF, Excel) duplicate the same business logic"
  - "Counting, labeling, or describing functions appear in more than one generator"
  - "A new report format is being added and needs the same logic as existing ones"
  - "An /improve audit flags duplication across reporting modules"
symptoms:
  - "count_issues() duplicated in core.py, trend.py, and cli.py with inconsistent category coverage"
  - "score_label() logic repeated in html.py, pdf.py, and excel.py with threshold drift risk"
  - "describe_issue() built inline in api.py and excel.py with identical string formatting"
  - "FixSuggestion construction boilerplate repeated 3x across modules"
  - "ID-column detection heuristic duplicated in two detection.py functions"
root_cause: logic_error
resolution_type: code_fix
related_components:
  - documentation
tags:
  - deduplication
  - shared-helpers
  - multi-format
  - report-generators
  - core-module
  - separation-of-concerns
  - dry-principle
  - python-cli
---

# Extract shared business logic from multi-format report generators

## Context

A Python CLI tool (Data Hygiene Auditor) generates audit reports in three formats: HTML (f-string template), PDF (ReportLab), and Excel (openpyxl). Over time, format-independent business logic -- counting issues, computing score labels, describing issues in plain text, constructing FixSuggestion objects, detecting ID columns -- was duplicated across format-specific modules. Each copy drifted slightly: the CLI's counting loop missed fuzzy duplicates entirely (session history), and threshold values in score-label if/elif chains risked diverging across generators.

An `/improve` audit identified 16 code quality findings. Most involved this duplication pattern. The challenge was separating format-independent logic (which belongs in a shared module) from format-specific rendering (which must stay in each generator).

This is the behavioral companion to the [centralized brand palette module](centralized-brand-palette-module.md), which solved the same problem for data constants (color tokens). This doc covers extracting shared *functions* -- the logic that operates on data, not the tokens themselves.

## Guidance

Separate format-independent business logic from format-specific rendering, then extract the business logic to a central shared module (`core.py`). Leave rendering code in each generator.

### 1. Identify what is format-independent

Logic that produces plain strings, numbers, booleans, or data structures -- not markup, styled objects, or format-specific widgets -- is a candidate for extraction.

```python
# core.py -- format-independent, returns plain data
def score_label(score: float) -> str:
    if score >= 90: return "Excellent"
    if score >= 75: return "Good"
    if score >= 50: return "Needs Attention"
    return "Poor"

def describe_issue(issue_type: str, detail: dict, issue: dict | None = None) -> str:
    """One-line plain-text description of an issue."""
    # Returns a string, not HTML or a reportlab Paragraph

def count_issues(results: dict) -> dict:
    """Count all issues across all sources (field issues, phantom dupes, fuzzy dupes, schema violations)."""
    # Returns {'total': N, 'High': N, 'Medium': N, 'Low': N, 'schema': N}
```

### 2. Leave format-specific rendering in each generator

HTML table rows, ReportLab `Paragraph` objects, and openpyxl `Font`/`PatternFill` styling are fundamentally different representations. Do not abstract across them.

```python
# html.py -- keeps its own HTML rendering
label = score_label(overall)
html += f'<span class="badge {label.lower()}">{label}</span>'

# pdf.py -- keeps its own ReportLab rendering
label = score_label(overall)
story.append(Paragraph(f"<b>Health Score: {overall}/100</b> -- {label}", style))

# excel.py -- keeps its own openpyxl rendering
label = score_label(overall)
cell.font = Font(color=P.xl(color_map[label]))
```

### 3. Extract local helpers for format-specific boilerplate

When boilerplate is repeated within a single format module but is not reusable across formats, extract a private helper within that module.

```python
# excel.py -- private helper, not in core.py
def _write_row(ws, row: int, values: list, font=None, fill=None):
    for col, val in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=val)
        if font: cell.font = font
        if fill: cell.fill = fill
```

### 4. Use classmethods to eliminate construction boilerplate

When the same dict-to-object construction appears in multiple modules, add a classmethod.

```python
@dataclass
class FixSuggestion:
    column: str
    description: str
    code: str

    @classmethod
    def from_dict(cls, d: dict | None) -> "FixSuggestion | None":
        if not d:
            return None
        return cls(column=d.get("column", ""), description=d["description"], code=d["code"])
```

### 5. Handle circular imports with lazy imports

When a downstream module (e.g., `trend.py`) needs a function from `core.py` but `core.py` already imports from that module's sibling, use a lazy import inside the function body.

```python
# trend.py
def compute_trend(results, baseline):
    from .core import count_issues  # lazy to avoid circular import
    current = count_issues(results)
```

### 6. Fix API visibility

If a function prefixed with `_` (private) is imported by other modules, rename it to remove the underscore. Private functions should not cross module boundaries. When renaming, update `__init__.py` exports and all import sites.

### 7. Use .get() for Counter-style dicts

When a counting function returns a dict keyed by values present in the data (like severity levels), always access with `.get(key, 0)`. Direct access raises `KeyError` when a severity level has zero occurrences. (session history)

## Why This Matters

- **Silent drift.** Duplicated business logic drifts without warning. The CLI's counting loop missed fuzzy duplicates entirely -- only discovered when all three implementations were compared side-by-side. (session history)
- **Net code reduction.** This refactor removed 49 lines across 13 files while adding new shared functions. The deduplication more than pays for the new API surface.
- **Cheaper new formats.** A future Markdown or JSON report generator can call `core.score_label()` and `core.describe_issue()` immediately, instead of reverse-engineering logic from an existing generator.
- **Clear boundary.** If it returns plain data, it goes in `core.py`; if it returns markup or styled objects, it stays in the format module. This heuristic is easy to follow and review.

## When to Apply

- A Python project has multiple report generators (HTML, PDF, Excel, Markdown, JSON) that share business logic
- An `/improve` or code review audit flags duplication across format-specific modules
- Adding a new output format and noticing you are copy-pasting logic from an existing generator
- Count/label/description functions appear in more than one module with identical or near-identical implementations
- A data class is constructed from a dictionary in 3+ places with the same field mapping

## Examples

**Before -- duplicated score_label logic with threshold drift:**

```python
# html.py
if score >= 90: label = "Excellent"
elif score >= 75: label = "Good"
elif score >= 50: label = "Needs Attention"
else: label = "Poor"

# pdf.py (same logic, different threshold bug risk)
if score >= 90: label = "Excellent"
elif score >= 70: label = "Good"  # BUG: 70 vs 75
elif score >= 50: label = "Needs Attention"
else: label = "Poor"
```

**After -- shared function, format-specific wrapping:**

```python
# core.py -- single source of truth
def score_label(score: float) -> str:
    if score >= 90: return "Excellent"
    if score >= 75: return "Good"
    if score >= 50: return "Needs Attention"
    return "Poor"

# html.py
label = score_label(overall)

# pdf.py
label = score_label(overall)
```

**Before -- FixSuggestion constructed 3x with identical boilerplate:**

```python
# In api.py, html.py, and excel.py:
fix = issue.get('fix')
if fix:
    suggestion = FixSuggestion(
        column=fix.get("column", ""),
        description=fix["description"],
        code=fix["code"],
    )
```

**After -- classmethod:**

```python
suggestion = FixSuggestion.from_dict(issue.get('fix'))
```

**Before -- CLI counting missed fuzzy duplicates (session history):**

```python
# cli.py -- only counted field issues and phantom dupes
total = 0
for sheet in results["sheets"].values():
    for field in sheet["fields"].values():
        total += len(field["issues"])
    total += len(sheet["phantom_duplicates"])
    # MISSING: fuzzy_duplicates and schema_violations
```

**After -- shared count_issues covers all sources:**

```python
# core.py
def count_issues(results):
    counts = {'total': 0, 'High': 0, 'Medium': 0, 'Low': 0, 'schema': 0}
    for sheet in results['sheets'].values():
        for field in sheet['fields'].values():
            for issue in field['issues']:
                counts['total'] += 1
                counts[issue['severity']] += 1
        for d in sheet['phantom_duplicates']:
            counts['total'] += 1
            counts[d['severity']] += 1
        for f in sheet.get('fuzzy_duplicates', []):
            counts['total'] += 1
            counts[f['severity']] += 1
        for sv in sheet.get('schema_violations', []):
            counts['total'] += 1
            counts[sv['severity']] += 1
            counts['schema'] += 1
    return counts
```

## Related

- [centralized-brand-palette-module.md](centralized-brand-palette-module.md) -- companion pattern that centralizes visual tokens; this doc extends the same principle to business logic
- `data_hygiene_auditor/core.py` -- shared format-independent business logic (score_label, describe_issue, issue_example, count_issues, describe_schema_violation)
- `data_hygiene_auditor/reporting/palette.py` -- centralized brand tokens
- `data_hygiene_auditor/api.py` -- FixSuggestion.from_dict classmethod
- `data_hygiene_auditor/detection.py` -- _identify_id_columns extracted helper
- `data_hygiene_auditor/reporting/excel.py` -- _write_row format-specific helper
