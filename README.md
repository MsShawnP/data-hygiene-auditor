# Data Hygiene Auditor

Phone numbers stored seven different ways in the same column. "TBD" sitting in a status field for three years. A customer record that looks unique until you notice that whitespace and casing are the only things separating it from four others. These are the issues consultants inherit when they take over someone else's spreadsheet — and the ones nobody finds until they're already in production.

The Data Hygiene Auditor is a Python CLI that scans Excel workbooks for the specific real-world failure modes that show up in actual consulting engagements: mixed-format inconsistencies, fields used for the wrong purpose, placeholder values that escaped into production, and phantom duplicates hiding behind cosmetic differences.

A single run produces three reports tailored to three audiences: an **HTML report** for the stakeholder meeting, an **Excel findings file** for the person doing the cleanup, and a **PDF** for the deliverable folder.

## What It Detects

**Mixed Formats** — Identifies dates, phone numbers, and currency values stored in inconsistent formats within the same column. For example, `2023-01-15` alongside `Jan 15, 2023` and `01/15/2023` in one date field. The auditor recognizes 6 date patterns, 7 phone patterns, and 6 currency patterns.

**Misused Fields** — Flags data stored in the wrong column: reference codes in name fields, free text in currency columns, invalid email addresses, and mixed boolean representations (`Y/N` vs `1/0` vs `Active/Inactive` in the same field).

**Placeholder Floods** — Detects test values (`Test`, `N/A`, `TBD`, `000-000-0000`) that persisted into production, as well as suspiciously repeated values that may indicate defaults that were never updated.

**Phantom Duplicates** — Finds records that appear different on the surface due to casing, whitespace, or punctuation but represent the same entity after normalization. ID columns are automatically excluded from matching, so two records with different surrogate keys but identical content are still caught.

**Fuzzy Duplicates** — Goes beyond normalization with fingerprint clustering (catches token reordering like "Smith John" vs "John Smith") and Levenshtein distance matching (catches typos like "Johnathan" vs "Jonathon"). Configurable similarity threshold.

**Completeness Baseline** — Every field receives a null/missing analysis with severity rating, including detection of whitespace-only values that look populated but carry no data.

**Health Score** — Every sheet and the overall file receive a 0-100 hygiene score. 90+ is clean, 70-89 needs attention, below 70 has significant issues. The score appears in all three reports and on the CLI.

**Fix Suggestions** — Every finding includes a copyable pandas code snippet: date normalization scripts, phone reformatting, placeholder replacement, dedup strategies. The HTML report has one-click copy buttons; the Excel report adds a "Suggested Fix" column.

## Design Decisions

- **Automatic field classification.** Each column is inferred as one of: date, phone, currency, email, ID, name, categorical, freetext, or zipcode. The correct validation rules are applied based on the inferred type — date-format checks don't run against phone fields, and vice versa.
- **Severity ratings on every finding.** High, Medium, and Low thresholds are calibrated to the issue type (e.g., >30% format inconsistency = High; 10–30% = Medium).
- **Plain-English impact statements.** Every finding includes a "Why this matters" explanation written for non-technical stakeholders who need to understand the business consequence, not just the statistic.
- **Multi-sheet support.** All sheets in a workbook are audited independently.

## Output

A single run produces three files:

| Output | Use Case |
|--------|----------|
| `*_audit_report.html` | Visual walkthrough with severity badges, format distribution tables, null-completeness bars, and impact explanations. Designed to present to a client or stakeholder. |
| `*_audit_findings.xlsx` | One row per issue. Frozen header, auto-filter, severity color-coding. Built for the person who needs to work through the fixes. |
| `*_audit_report.pdf` | Same substance as the HTML in a format suitable for email attachments and formal deliverables. |

## See It In Action

Real outputs from a real run are committed to this repo so you can preview them without installing anything. They were produced from the deliberately-messy demo file under [samples/](samples/) — a 30-row, 2-sheet workbook that exercises every detection category. The run reported **59 issues** (23 High, 20 Medium, 16 Low).

| File | Description |
|------|-------------|
| [samples/input/sample_messy_data.xlsx](samples/input/sample_messy_data.xlsx) | Input — the messy workbook |
| [samples/output/sample_messy_data_audit_report.html](samples/output/sample_messy_data_audit_report.html) | HTML stakeholder report |
| [samples/output/sample_messy_data_audit_findings.xlsx](samples/output/sample_messy_data_audit_findings.xlsx) | Excel findings file |
| [samples/output/sample_messy_data_audit_report.pdf](samples/output/sample_messy_data_audit_report.pdf) | PDF deliverable |

![Summary cards at the top of the HTML report](samples/output/screenshots/summary_cards.png)

*Top of the HTML report. The four cards show total issue count and a breakdown by severity, generated from a 30-row, 2-sheet sample workbook designed to exercise every detection category. Below the summary, findings are organized by sheet and by column.*

![Multiple stacked findings on a single column](samples/output/screenshots/multiple_findings_one_column.png)

*One column (`FirstName`) with multiple stacked issues at different severities. The yellow progress bar shows the missing-data rate (13.3%, with 1 whitespace-only value), and four findings are stacked underneath: a LOW high-missing-rate flag, a HIGH "code stuffed in name field" flag with a concrete example from row 16, a MEDIUM placeholder detection for "Test", and a LOW placeholder detection for "TBD".*

![Format distribution table on the Phone column](samples/output/screenshots/format_distribution_table.png)

*The `Phone` column finding showing a HIGH severity Mixed Phone Formats issue: 17 of 26 values deviate from the dominant format. The embedded table breaks down the actual format distribution found in the data, so a reader can see exactly which variants are present and how often. Below it, additional findings on the same column flag a placeholder ("TBD") and a suspicious repetition ("(555) 123-4567" appearing 3 times).*

To regenerate the outputs locally:

```
python audit.py --input samples/input/sample_messy_data.xlsx --output samples/output/
```

## Installation

```
pip install .
```

Or install dependencies directly:

```
pip install -r requirements.txt
```

## Usage

```
data-hygiene-audit --input <file> --output <report_directory>
```

Or run directly:

```
python audit.py --input <file> --output <report_directory>
```

Supports `.xlsx`, `.xls`, `.csv`, and `.tsv` files.

### Options

| Flag | Description |
|------|-------------|
| `--input`, `-i` | Path to the file to audit — `.xlsx`, `.csv`, or `.tsv` (required) |
| `--output`, `-o` | Directory for generated reports (required) |
| `--json` | Also output the raw findings as structured JSON |
| `--threshold`, `-t` | Fuzzy duplicate similarity threshold, 0.0–1.0 (default: 0.85) |
| `--schema`, `-s` | Path to a schema JSON for type/completeness validation |
| `--generate-schema` | Infer types from the data and save a schema JSON to the given path |
| `--baseline`, `-b` | Path to a previous audit JSON for trend comparison (shows deltas) |
| `--quiet`, `-q` | Suppress all terminal output (just write report files) |
| `--force` | Process files exceeding the 2M row safety limit |
| `--version`, `-V` | Print version and exit |

### Example

```
python audit.py --input samples/input/sample_messy_data.xlsx --output ./reports
```

```
  Data Hygiene Auditor
  Auditing: samples/input/sample_messy_data.xlsx

  [1/2] Analyzed sheet: Customers  (score: 42)
  [2/2] Analyzed sheet: Orders  (score: 68)

  Generating reports...
    HTML  -> ./reports/sample_messy_data_audit_report.html
    Excel -> ./reports/sample_messy_data_audit_findings.xlsx
    PDF   -> ./reports/sample_messy_data_audit_report.pdf

  Health Score: 55/100
  59 issues found  —  High: 23 | Medium: 20 | Low: 16
```

## Use as a Library

After `pip install .`, the auditor is importable as a Python library with typed results:

```python
from data_hygiene_auditor import audit_file

result = audit_file("customers.xlsx")
print(f"Health Score: {result.overall_score}/100")

for sheet in result.sheets:
    print(f"\n{sheet.name}: {sheet.health_score}/100")
    for finding in sheet.findings:
        print(f"  [{finding.severity}] {finding.field}: {finding.description}")
        if finding.fix:
            print(f"    Fix: {finding.fix.description}")
```

The `audit_file()` function returns an `AuditResult` with typed access to all findings:

```python
result = audit_file("data.xlsx")

# Filter by severity
critical = result.high_issues
warnings = result.medium_issues

# Access raw dict for custom processing
raw = result.to_dict()

# Generate reports programmatically
result.generate_html("report.html")
result.generate_excel("findings.xlsx")
result.generate_pdf("report.pdf")

# Adjust fuzzy matching sensitivity
strict = audit_file("data.xlsx", fuzzy_threshold=0.95)
loose = audit_file("data.xlsx", fuzzy_threshold=0.70)
```

Works in Jupyter notebooks — call `audit_file()` in a cell and explore the typed results interactively.

## Regenerating the Sample Data

`generate_sample.py` recreates the deliberately-messy demo workbook at `samples/input/sample_messy_data.xlsx`. Run it if you want to modify the demo data or verify that generation is reproducible. The committed outputs in [samples/output/](samples/output/) can then be regenerated with the command shown in [See It In Action](#see-it-in-action).

```
python generate_sample.py
```

## Requirements

- Python 3.9+
- pandas
- openpyxl
- reportlab

## License

MIT — see [LICENSE](LICENSE)
