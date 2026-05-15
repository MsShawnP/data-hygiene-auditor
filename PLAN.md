# Data Hygiene Auditor — Improvement Plan

**Source:** Full project audit (2025-05-15)
**Tier:** Medium
**Status:** Sprint 1

---

## Sprint 1: Quick Wins

### Goal: CSV Support
**Category:** Close gap
**Priority:** 1

#### Objective
Accept .csv files in addition to .xlsx. Every competitor handles CSV — this is table stakes.

#### Success Criteria
- `python audit.py --input data.csv --output ./reports` works
- All detection engines run identically on CSV and Excel input
- Multi-file input not required — just single CSV support

#### Context
Phase 3: CSV is the only format supported by all 7 competitors but missing from this project. Phase 2: Input validation (item #7) is also missing — handle both together.

---

### Goal: Quick Fixes Batch
**Category:** Foundational
**Priority:** 2

#### Objective
Fix the 6 low-effort issues identified in Phase 2 that require ~1 line each.

#### Success Criteria
- [ ] `why` text escaped with `_h()` in HTML (lines 844, 864) and `_p()` in PDF (lines 1127, 1137)
- [ ] Dependency versions pinned in requirements.txt
- [ ] `blank_count` / `whitespace_only` overlap fixed — predicates made disjoint
- [ ] Dead code removed (`SEVERITY_COLORS` dict)
- [ ] HTML generation switched from `html +=` to list + `''.join()`
- [ ] Input file type validated before processing
- [ ] `why` text fallback at line 568 fixed (don't silently use date explanation for non-date types)

#### Context
Phase 2 items #1-8. All rated effort 1. Security, correctness, and performance fixes with zero risk.

---

### Goal: Progress + Colored CLI
**Category:** Close gap
**Priority:** 3

#### Objective
Add a progress indicator and colored severity output so the CLI feels like a polished tool instead of a bare script.

#### Success Criteria
- Per-sheet progress shown during analysis
- Per-report progress shown during generation
- Final summary uses colored severity counts (red/yellow/green)
- Works on Windows (this is a Windows project)

#### Context
Phase 2 item #4. Phase 3: OpenRefine, ydata-profiling, and Soda all provide clear progress feedback.

---

### Goal: pyproject.toml + Installable Package
**Category:** Foundational
**Priority:** 4

#### Objective
Add standard Python packaging so the project can be installed with `pip install .` and has a proper entry point.

#### Success Criteria
- `pyproject.toml` exists with metadata, dependencies, and entry point
- `pip install .` works and provides a `data-hygiene-audit` CLI command
- `requirements.txt` kept for compatibility but references pyproject.toml deps
- README updated with install instructions

#### Context
Phase 2 DevEx finding: no pyproject.toml or setup.py. Portfolio visitors expect standard packaging.

---

## Decomposition: Sprint 1

Goal: Ship all quick wins so the project feels professional and covers table-stakes gaps.

All 4 goals are independent of each other — work in any order. Within each goal, sub-tasks are sequential.

### A. Quick Fixes Batch

- [ ] A1: Escape `why` text in HTML and PDF reports
    - Depends on: none
    - Done when: `_h()` wraps `why` at lines 844, 864 in HTML; `_p()` wraps `why` at lines 1127, 1137 in PDF
- [ ] A2: Fix blank_count / whitespace_only overlap
    - Depends on: none
    - Done when: `blank_count` = truly empty strings only (len 0); `whitespace_only` = strings with len > 0 that are all whitespace; the two sets are disjoint; `total_missing` still includes both
- [ ] A3: Switch HTML generation from string concat to list + join
    - Depends on: none
    - Done when: `generate_html` uses `parts = []` / `parts.append()` / `''.join(parts)` instead of `html +=`; output HTML is identical
- [ ] A4: Cleanup — pin deps, remove dead code, fix why fallback
    - Depends on: none
    - Done when: `requirements.txt` has pinned versions (e.g., `pandas>=2.0`); `SEVERITY_COLORS` dict deleted; line 568 fallback raises or uses a generic explanation instead of silently using date text
- [ ] A5: Verify all fixes
    - Depends on: A1-A4
    - Done when: `python audit.py --input samples/input/sample_messy_data.xlsx --output samples/output/` runs successfully and produces all 3 reports

### B. CSV Support

- [ ] B1: Add input file validation + CSV reading path
    - Depends on: none
    - Done when: `.csv` files read with `pd.read_csv`; `.xlsx` files read as before; unsupported extensions get a clear error message naming the supported formats
- [ ] B2: Create a CSV version of sample data for testing
    - Depends on: B1
    - Done when: `samples/input/sample_messy_data.csv` exists (exported from the Customers sheet); running audit on it produces findings
- [ ] B3: Verify detection parity between CSV and Excel
    - Depends on: B1, B2
    - Done when: CSV audit of the Customers sheet produces the same issue types and severity counts as Excel audit of the same sheet

### C. Progress + Colored CLI

- [ ] C1: Add colored severity output to final summary
    - Depends on: none
    - Done when: `High: N` prints in red, `Medium: N` in yellow, `Low: N` in green in terminal; falls back gracefully on terminals without color support
- [ ] C2: Add per-sheet and per-report progress indicators
    - Depends on: none
    - Done when: output shows `Analyzing sheet 1/2: Customers...` and `Generating HTML report...` with timing or completion feedback

### D. pyproject.toml + Installable

- [ ] D1: Create pyproject.toml with metadata, dependencies, and CLI entry point
    - Depends on: none
    - Done when: `pip install .` succeeds and `data-hygiene-audit --help` prints usage
- [ ] D2: Update README with install instructions
    - Depends on: D1
    - Done when: README includes `pip install .` method alongside the existing `pip install -r requirements.txt` method

### Sprint 1 complete when:
- [ ] All sub-tasks checked off
- [ ] `data-hygiene-audit --input samples/input/sample_messy_data.xlsx --output samples/output/` produces all 3 reports with correct findings
- [ ] `data-hygiene-audit --input some_file.csv --output ./reports` works on a CSV file
- [ ] Terminal output shows progress and colored summary
- [ ] Commit and push

---

## Sprint 2: Foundation

### Goal: Package Restructure
**Category:** Foundational
**Priority:** 5

#### Objective
Split the 1,227-line monolith into a proper package structure.

#### Success Criteria
- `data_hygiene_auditor/` package with: `detection/` (engines), `reporting/` (html, excel, pdf), `models.py` (dataclasses), `cli.py` (entrypoint)
- Each detection engine is independently importable and testable
- Adding a new detection rule doesn't require touching renderers
- Adding a new output format doesn't require understanding detection logic
- `audit.py` in root becomes a thin wrapper or is removed in favor of entry point

#### Context
Phase 2 Architecture: critical findings about monolithic structure, untyped dicts, triplicated rendering. Phase 3: importable API is table stakes — package structure enables it.

---

### Goal: Test Suite
**Category:** Foundational
**Priority:** 6

#### Objective
Add pytest-based tests covering each detection engine and edge cases.

#### Success Criteria
- pytest in dependencies
- Tests for: `infer_field_type`, `analyze_nulls`, `analyze_mixed_formats`, `analyze_wrong_purpose`, `analyze_placeholders`, `analyze_phantom_duplicates`
- Edge case tests: single-row sheets, all-null columns, all-ID columns, empty sheets
- Integration test: run full audit on sample data, verify issue counts match expected
- `generate_sample.py` output used as a test fixture

#### Context
Phase 2 Tests: critical — zero coverage. Must come after package restructure (test modules, not a monolith).

---

### Goal: CI/CD with GitHub Actions
**Category:** Foundational
**Priority:** 7

#### Objective
Automate linting and testing on every push.

#### Success Criteria
- `.github/workflows/ci.yml` runs on push and PR
- Steps: install deps, lint with ruff, run pytest
- Badge in README showing CI status
- Ruff config in pyproject.toml

#### Context
Phase 2 DevEx: no CI. Portfolio credibility signal — a green badge says "this is maintained."

---

## Sprint 3: The "Wow"

### Goal: Data Quality Health Score
**Category:** Double down
**Priority:** 8

#### Objective
Add a single 0-100 "hygiene score" per sheet and overall. The number at the top of every report.

#### Success Criteria
- Score algorithm considers: issue count, severity distribution, completeness rates, duplicate rate
- Score displayed prominently in HTML report header, PDF first page, Excel summary sheet, and CLI output
- Score is intuitive: 90+ = clean, 70-89 = needs attention, <70 = significant issues
- No competitor does this — it's a unique differentiator

#### Context
Phase 3: No competitor produces a single quotable number. Phase 4: This is the "wow" for stakeholder meetings — "your data scores a 62."

---

### Goal: Interactive HTML Report
**Category:** Double down
**Priority:** 9

#### Objective
Transform the static HTML report into an interactive, explorable interface.

#### Success Criteria
- Filter findings by severity (High / Medium / Low toggle)
- Collapsible sections per sheet and per field
- Table of contents with anchor links
- Search/filter by column name or issue type
- All interactivity is client-side JS (no server needed — still a single HTML file)
- Mobile-responsive
- Maintains the existing dark theme aesthetic

#### Context
Phase 2 UX: static report is unusable at 100+ issues. Phase 3: ydata-profiling, Great Expectations, and OpenRefine all have interactive reports. Phase 4: combining interactivity with your unique severity + explanation features creates something no competitor has.

---

### Goal: Vectorize Phantom Duplicate Detection
**Category:** Close gap + Double down
**Priority:** 10

#### Objective
Replace the row-by-row Python MD5 hashing with vectorized pandas operations.

#### Success Criteria
- 100K rows completes in under 30 seconds (currently estimated 10+ minutes)
- Same detection accuracy as before (test suite validates this)
- Also pre-compile and combine regex patterns in mixed-format analysis

#### Context
Phase 2 Performance: critical — `.apply(lambda, axis=1)` is a pure Python loop. Phase 3: every competitor handles 100K+ rows routinely. This project will choke.

---

## Sprint 4: Extend the Moat

### Goal: Fuzzy Duplicate Matching
**Category:** Double down
**Priority:** 11

#### Objective
Upgrade phantom duplicate detection from normalize-and-match to real fuzzy deduplication.

#### Success Criteria
- Fingerprint clustering (key collision) as default
- Optional Levenshtein distance matching for near-matches
- Configurable similarity threshold
- Results show which fields differ and by how much
- Significantly more duplicates caught than current approach

#### Context
Phase 3: OpenRefine's text clustering (Levenshtein, fingerprint, metaphone, nearest-neighbor) is the gold standard for fuzzy dedup. Current approach catches case/whitespace only — misses typos, abbreviations, and phonetic matches.

---

### Goal: Importable Python API
**Category:** Close gap
**Priority:** 12

#### Objective
Expose `run_audit()` and related functions as a clean public API for programmatic use.

#### Success Criteria
- `from data_hygiene_auditor import audit_file` works after pip install
- Returns typed results (dataclasses, not nested dicts)
- Documented with docstrings and type hints
- Can be used in Jupyter notebooks
- README includes "Use as a library" section

#### Context
Phase 3: Most Python tools (ydata-profiling, pandera, Great Expectations) are importable libraries. CLI-only limits utility. Package restructure (Sprint 2) enables this for free.

---

## Future / Stretch

### Goal: AI-Powered Fix Suggestions
**Category:** Leapfrog
**Priority:** 13 (stretch)

#### Objective
Generate actionable fix scripts or transformation suggestions for each finding.

#### Success Criteria
- For mixed formats: suggest a normalization script (e.g., "standardize all phones to (XXX) XXX-XXXX")
- For placeholders: suggest replacement strategy
- For duplicates: suggest merge/dedup approach
- Output as copyable code snippets in the HTML report

#### Context
Phase 3 Category Trends: AI-powered fix suggestions are emerging but nobody does them well. This is the leapfrog opportunity — but only after foundation and presentation are solid.
