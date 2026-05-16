# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- CLI issue count now includes fuzzy duplicates and schema violations
- `AuditResult._raw` is a proper dataclass field (type-checker visible)

### Added
- Custom rule engine: define detection rules in JSON (`--rules` flag)
  - Conditions: `regex_match`, `not_regex_match`, `min_length`, `max_length`, `allowed_values`, `disallowed_values`, `max_missing_pct`
  - Target columns by regex pattern or explicit list
  - Findings integrated into all 3 report formats
- Column-level profiling: cardinality, uniqueness %, avg length, numeric range
  - Stats shown in HTML, Excel, PDF, and JSON output
  - `ColumnProfile` dataclass in typed API
- Multi-file / directory mode: `--input ./data/` audits all supported files
  - `run_multi_audit()` API for programmatic multi-file audits
- CI / pipeline integration
  - `--fail-under` flag: exit code 1 if score < threshold
  - `--sarif` flag: SARIF 2.1.0 output for GitHub Code Scanning
  - GitHub Action (`.github/actions/audit/action.yml`)
- `--version` / `-V` flag
- `--quiet` / `-q` flag to suppress terminal output
- `--export-fixes` flag: export remediation plan as CSV (sorted by severity, with fix code and assignee columns)
- `--force` flag to override the 2M row safety limit
- `count_issues()` shared helper for consistent issue counting
- Warning when fuzzy (Levenshtein) matching is skipped due to row count
- File size guard: warns at 500K rows, refuses at 2M without `--force`

### Changed
- Minimum Python version raised from 3.8 to 3.9

## [1.0.0] - 2026-05-09

### Added
- Schema validation via `--schema` flag with JSON schema files
- `--generate-schema` to infer and export a schema from audit results
- `--baseline` / `-b` for trend comparison against previous audits
- Trend deltas shown in CLI output and reports
- `--threshold` / `-t` flag for fuzzy duplicate similarity tuning
- Typed Python API (`audit_file()`, dataclass results, `py.typed`)
- Fuzzy duplicate detection (fingerprint clustering + Levenshtein)
- Health score algorithm (0–100, penalty-based)
- Interactive HTML report with collapsible sections
- Fix suggestion engine with copyable code snippets
- Vectorized detection for 3.4x speedup on large files
- CSV/TSV support alongside Excel
- PDF report output (reportlab)
- Excel findings export (sortable/filterable)
- Test suite (171 tests) and CI pipeline
- MIT license

[Unreleased]: https://github.com/MsShawnP/Data-Hygiene-Auditor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/MsShawnP/Data-Hygiene-Auditor/releases/tag/v1.0.0
