# DECISIONS

Durable choices with rationale. Most recent on top.

### 2026-07-27 — Spreadsheet outputs must sanitize formula injection
- **Why:** The `.xlsx` findings file and `--export-fixes` CSV are marketed
  as email-ready deliverables and embed user-supplied sheet names, column
  headers, and cell values. Any value starting with `=`, `+`, `-`, `@`, or
  a tab/CR executes as a formula when a recipient opens it (HYPERLINK/
  WEBSERVICE exfiltration, legacy DDE). openpyxl confirmed to write leading
  `=` as a live formula.
- **Scope:** Every string written to an Excel or CSV output. Route it
  through `core.sanitize_spreadsheet_cell()`.
- **Do not:** Write raw user-derived strings into a spreadsheet cell. HTML
  and PDF are exempt (they already escape via `html.escape` / saxutils).

### 2026-07-27 — Cross-output display logic lives in one core producer
- **Why:** Issue wording, health-score bands, and per-sheet issue counts
  were each duplicated across the HTML, PDF, Excel, API, and trend outputs
  and had drifted (divergent wording, repeated 90/70/40 thresholds). One
  source keeps every renderer in sync.
- **Scope:** `issue_headline()` (issue text), `score_band()` (band
  boundaries + `score_label`), `count_sheet_issues()` (per-sheet tally),
  `combine_overall_score()` (row-weighted multi-file score) — all in
  `core`.
- **Do not:** Re-implement per-issue-type text, re-test the 90/70/40 band
  thresholds, or re-count issues inside a renderer. Compose from the core
  helper and apply only medium-specific markup/colours locally.

### 2026-07-27 — `git fetch` before committing on `main`
- **Why:** This repo is worked from more than one machine. Starting a
  session on a stale local `main` produced 15 commits that then rejected on
  push against a remote already at v1.1.5; the rebase was recoverable but
  avoidable.
- **Scope:** Any session that will commit to `main`.
- **Do not:** Assume the local `main` is current — `git fetch` (or check
  divergence) at session start before doing work.
