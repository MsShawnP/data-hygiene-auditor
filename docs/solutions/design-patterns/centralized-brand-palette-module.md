---
title: Centralized brand palette module for multi-format report generators
date: 2026-05-20
category: design-patterns
module: data_hygiene_auditor.reporting
problem_type: design_pattern
component: tooling
severity: medium
applies_when:
  - "Python project generates reports in multiple formats (HTML, PDF, Excel)"
  - "A design system or brand kit defines canonical color tokens that must stay in sync"
  - "ReportLab, openpyxl, or HTML templates coexist in the same codebase"
  - "Code review reveals divergent hardcoded values across files for the same semantic color"
symptoms:
  - "PDF severity colors diverged from HTML (SevMedium used #c87222 instead of #ee8a2a)"
  - "Excel Summary sheet retained Arial font instead of Source Sans Pro"
  - "Same hex values duplicated across 3 report generators with no single source of truth"
root_cause: config_error
resolution_type: code_fix
related_components:
  - documentation
tags:
  - design-system
  - palette
  - reportlab
  - openpyxl
  - html-reports
  - brand-consistency
  - multi-format
---

# Centralized brand palette module for multi-format report generators

## Context

A Python CLI tool (Data Hygiene Auditor) generates audit reports in three formats: HTML (via f-string template), PDF (via ReportLab), and Excel (via openpyxl). Brand colors were hardcoded independently in each generator, causing silent drift. A multi-agent code review caught 3 bugs where the same semantic color had different hex values across formats. The Lailara LLC design system needed to be applied consistently across all three outputs.

## Guidance

Centralize all brand tokens in a single `palette.py` module, then adapt consumption to each format's hex convention:

### 1. Shared palette module

Define all brand tokens as Python string constants with `#`-prefixed CSS hex values. Create semantic aliases and a `xl()` helper for openpyxl.

```python
# palette.py

# --- Brand primaries ---
CHICAGO_20 = '#1f2e7a'
HONG_KONG_35 = '#158f75'
SINGAPORE_55 = '#ee8a2a'
RED_42 = '#cc100a'

# --- Tints ---
HONG_KONG_95 = '#e4f5f0'
SINGAPORE_95 = '#fdeee0'
RED_95 = '#fce8e7'

# --- London greyscale ---
INK = '#0d0d0d'
LONDON_20 = '#333333'
LONDON_85 = '#d9d9d9'
CANVAS = '#f5f3ee'

# --- Semantic aliases ---
SEV_HIGH = RED_42
SEV_MEDIUM = SINGAPORE_55
SEV_LOW = HONG_KONG_35
SEV_HIGH_BG = RED_95
SEV_MEDIUM_BG = SINGAPORE_95
SEV_LOW_BG = HONG_KONG_95

# --- Typography ---
FONT_SERIF = "'Playfair Display', Georgia, 'Times New Roman', serif"
FONT_SANS_EXCEL = 'Source Sans Pro'

def xl(hex_color: str) -> str:
    """Strip leading '#' for openpyxl, which expects bare hex."""
    return hex_color.lstrip('#')
```

### 2. HTML consumption

Populate CSS custom properties in a `:root` block using f-string interpolation from palette constants. Body CSS references them via `var()`.

```python
from . import palette as P

# In the HTML template f-string:
# :root {{
#     --chicago: {P.CHICAGO_20};
#     --low: {P.SEV_LOW};
#     --serif: {P.FONT_SERIF};
# }}
```

### 3. PDF consumption (ReportLab)

Use palette constants directly — ReportLab accepts `#`-prefixed hex natively.

```python
from . import palette as P

rl_colors.HexColor(P.SEV_LOW)        # '#158f75' works directly
rl_colors.HexColor(P.CHICAGO_20)     # table headers
rl_colors.HexColor(P.LONDON_85)      # grid borders
```

### 4. Excel consumption (openpyxl)

Use `P.xl()` to strip the `#` prefix — openpyxl expects bare hex strings.

```python
from . import palette as P

PatternFill("solid", fgColor=P.xl(P.CHICAGO_20))  # '1f2e7a'
PatternFill("solid", fgColor=P.xl(P.SEV_HIGH_BG)) # 'fce8e7'
Font(name=P.FONT_SANS_EXCEL, size=10)
```

### 5. Brand assertion tests

Verify palette colors appear in output and no legacy values remain.

```python
def test_css_uses_palette_canvas(self):
    # path = generated HTML report file path
    html = Path(path).read_text(encoding="utf-8")
    assert P.CANVAS in html
    assert P.CHICAGO_20 in html

def test_header_font_is_source_sans(self):
    # wb = openpyxl.load_workbook(generated_excel_path)
    ws = wb["Findings"]
    assert ws.cell(row=1, column=1).font.name == P.FONT_SANS_EXCEL

def test_xl_strips_hash(self):
    assert P.xl('#1f2e7a') == '1f2e7a'
    assert P.xl('1f2e7a') == '1f2e7a'
```

## Why This Matters

- Without a shared palette, colors drift between formats silently. The code review caught 3 bugs from exactly this problem — the same semantic color had different hex values in PDF vs Excel vs HTML.
- The `xl()` helper prevents a common openpyxl gotcha: `#`-prefixed hex values are silently accepted but produce wrong colors.
- Brand assertion tests catch regressions automatically, so future changes to any single generator immediately surface inconsistencies.
- Changing the brand palette becomes a single-file edit instead of a find-and-replace across 3 generators.

## When to Apply

- Any Python project generating reports in multiple formats (HTML, PDF, Excel, etc.)
- When applying a design system or brand kit to existing report generators
- When ReportLab, openpyxl, or HTML f-string templates coexist in the same project
- When a code review reveals color drift between output formats

## Examples

**Before** — duplicated constants, drifted values:

```python
# pdf.py — WRONG, should be #158f75
rl_colors.HexColor('#0e6e5a')

# excel.py — different value for same semantic color
PatternFill("solid", fgColor="D4EDDA")

# html.py — yet another value
--low: #28A745;
```

**After** — shared palette, format-aware helpers:

```python
# palette.py — single source of truth
HONG_KONG_35 = '#158f75'
SEV_LOW = HONG_KONG_35
SEV_LOW_BG = '#e4f5f0'

# pdf.py
rl_colors.HexColor(P.SEV_LOW)

# excel.py
PatternFill("solid", fgColor=P.xl(P.SEV_LOW_BG))

# html.py (in CSS :root f-string)
--low: {P.SEV_LOW};
```

## Related

- `data_hygiene_auditor/reporting/palette.py` — the implementation
- `tests/test_branding.py` — brand assertion tests (12 tests)
- DECISIONS.md entry: "Single-file HTML report with client-side JS" — related constraint on HTML report format
