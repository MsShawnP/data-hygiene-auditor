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
