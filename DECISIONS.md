# DECISIONS

Durable choices with rationale. Most recent on top.

### 2026-08-07 — HTML/PDF report byte-nondeterminism (fixed 2026-08-10)

Two distinct sources made the same input produce different report bytes
run-to-run. Both are now fixed; a third (the xlsx envelope) is a documented
residual.

- **Source 1 — set-iteration order (FIXED).** The HTML renderer built each
  field's `data-severities` attribute from a Python `set`, so it emitted in
  hash order (`"Low Medium High"` vs `"High Low Medium"`). Now sorted to a
  fixed High>Medium>Low order before emitting (`reporting/html.py`).
- **Source 2 — generation timestamp (FIXED).** `core.py` set `audit_timestamp`
  from `datetime.now()` — shown in the HTML/PDF header and footer — a
  wall-clock value that changes every run. It now honors `SOURCE_DATE_EPOCH`
  (the reproducible-builds standard): when set, the timestamp is derived from
  that UTC epoch; otherwise it stays wall-clock. Committed samples are
  regenerated with `SOURCE_DATE_EPOCH=1785888000` (2026-08-05, the 1.3.0
  release date) — see `scripts/regenerate_samples.sh`.
- **Correction to the original note.** The first version of this entry said
  `PYTHONHASHSEED=0` produced a byte-identical diff. That cannot be the whole
  mechanism — a wall-clock timestamp survives any hash seed. Either the two
  compared runs happened to land in the same second, or that comparison masked
  the timestamp line. Source 2 is why a hash-seed pin looked sufficient and
  was not.
- **Residual — xlsx envelope (NOT fixed).** openpyxl stamps wall-clock times
  into `docProps/core.xml` `modified` (it overrides a pinned value at save) and
  into every zip member's mtime. The findings workbook's *content* is otherwise
  reproducible, but its raw bytes are not byte-lockable without openpyxl-specific
  surgery (rewriting the zip corrupts the file — attempted and reverted).
- **Verify:** generate twice in separate processes with `SOURCE_DATE_EPOCH` set
  and no `PYTHONHASHSEED`; the `.html` and `.pdf` bytes match.
- **Do not:** add a byte-lock on the `.xlsx` output; do treat `.html`/`.pdf` as
  reproducible only when `SOURCE_DATE_EPOCH` is pinned.

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
