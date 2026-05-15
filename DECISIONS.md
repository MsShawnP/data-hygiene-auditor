# Decisions Log

## 2025-05-15: Package restructure — thin shim pattern
**Context:** Restructured 1355-line `audit.py` monolith into `data_hygiene_auditor/` package (7 modules).
**Decision:** Keep `audit.py` as a thin re-export shim so `from audit import run_audit` and `python audit.py` still work.
**Rationale:** Zero breaking changes for existing users. The shim is ~30 lines and trivially maintained.

## 2025-05-15: Health score algorithm — penalty-based
**Context:** Needed a 0-100 score that's intuitive (90+ clean, 70-89 attention, <70 serious).
**Decision:** Start at 100, deduct per issue: High=-3, Medium=-1.5, Low=-0.5, plus penalties for missing data and duplicates.
**Rationale:** Additive scoring (building up from 0) requires knowing the max possible issues. Penalty-based is simpler, always meaningful, and naturally caps at 0.

## 2025-05-15: Fuzzy matching — built-in, no external deps
**Context:** Sprint 4 needed fuzzy dedup. Options: thefuzz/rapidfuzz library, or built-in Levenshtein.
**Decision:** Implemented Levenshtein from scratch + fingerprint clustering. No new dependency.
**Rationale:** Keeps install lightweight (pandas/openpyxl/reportlab already heavy enough). Pairwise Levenshtein capped at 500 unmatched rows to avoid O(n²) explosion. Fingerprint clustering (sort tokens, strip punctuation) catches the most common fuzzy cases with zero performance cost.

## 2025-05-15: Fix suggestions — deterministic templates, not LLM
**Context:** "AI-Powered Fix Suggestions" stretch goal. Could use an LLM or generate code deterministically.
**Decision:** Deterministic pandas code templates filled with actual field names and values from the audit.
**Rationale:** No API key needed, works offline, instant, and the code is always syntactically valid. The audit already knows the problem and the dominant format — an LLM would just add latency and cost for the same output.

## 2025-05-15: Single-file HTML report with client-side JS
**Context:** Interactive HTML report needs filters, search, collapsible sections.
**Decision:** All CSS and JS inline in one HTML file. No external dependencies, no build step.
**Rationale:** Report must be shareable as a single file (email, Slack, etc.). Client-side JS means no server needed. Dark theme with accent color matches the audit-tool aesthetic.

## 2025-05-15: Vectorize detection — pandas .str over Python loops
**Context:** 100K-row benchmark showed 18.6s runtime, with all 6 detection functions bottlenecked on per-element Python iteration.
**Decision:** Replace all `[str(v) for v in values]` patterns with `Series.dropna().astype(str).str.strip()` and `Series.str.match()`. Replace `df.apply(lambda col: col.map(normalize))` with chained `.str` operations.
**Rationale:** 3.4x speedup (18.6s → 5.5s) with zero behavioral changes. Pandas vectorized string ops delegate to compiled C — the improvement is free once you match the API.

## 2025-05-15: Schema validation — shorthand + full form JSON
**Context:** Needed a schema format for validating expected column types, required columns, and completeness thresholds.
**Decision:** JSON schema with shorthand (`"col": "type"`) and full form (`"col": {"type": "phone", "required": true, "max_missing_pct": 5.0}`). Global columns with per-sheet overrides under `"sheets"`.
**Rationale:** Shorthand lowers the entry barrier — users can start with `{"columns": {"Phone": "phone"}}` and add constraints incrementally. Per-sheet overrides handle multi-sheet Excel files where the same column name has different semantics.

## 2025-05-15: Trend comparison — baseline JSON approach
**Context:** Users want to track data quality over time. Options: embedded database, file-pair comparison, or persistent store.
**Decision:** Compare current audit against a previous `--json` output passed via `--baseline`. No database, no state management.
**Rationale:** Stateless design — the user controls storage. Works with any CI pipeline (save JSON as artifact, pass to next run). Zero new dependencies. Handles new/removed sheets gracefully.

## 2025-05-15: CLI output — ASCII-only for Windows compatibility
**Context:** Trend display initially used Unicode arrows (↑↓) which fail on Windows cp1252 terminals.
**Decision:** Use `+N`/`-N` format in CLI. Keep Unicode in HTML reports (which declare UTF-8).
**Rationale:** The project runs on Windows. Terminal encoding limits are real. HTML has no such constraint.
