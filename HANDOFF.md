# HANDOFF

Session-to-session continuity for data-hygiene-auditor. Most recent entry on top.

## 2026-07-28 — un-pinned defect, fix not written

`TestPaletteModule.test_severity_aliases_match` asserted `SEV_HIGH == RED_42`
and two siblings. `palette.py:29-31` defines those names *as* those aliases, so
all three were tautologies that could not fail for any palette. The first also
asserted the thing the design system forbids.

- [ ] **Red-42 used as a background fill.** `reporting/html.py:246,356` plus
      `_SHEET_COLORS`/`_OVERALL_COLORS` fill 23 severity badges, 2 sheet-score
      chips and 1 filter button with Red-42 — 5 CSS declarations. Red-42 is ink:
      text and 1px rules, never a fill. Port the convention `pdf.py:127` and
      `excel.py:68` already use: a Red-95 (`#fce8e7`) surface with Red-18 text.
      Test: `tests/test_branding.py` —
      `test_red_42_is_never_a_background_fill_in_the_generated_css`, marked
      `xfail(strict=True)`. It resolves the CSS custom properties before
      matching, so it catches `var(--high)` as well as the raw hex, and it
      XPASSes and fails the suite the moment the fills are ported. Do not
      remove the marker without doing the fix.

Also recorded this session: the serif display scale is rem-based and diverges
from the DS px steps — written up in CLAUDE.md as a deliberate deviation, not a
defect. No production logic changed. 262 passed, 1 xfailed.

## 2026-07-27 21:05

**Started from:** Local `main` at v1.1.4; ran `/improve` + code review + UI review on the package. (Remote had silently advanced to v1.1.5 on another machine — discovered at push time.)

**Did:** Fixed every Important + Critical review finding, one commit + regression test each — spreadsheet formula injection (Excel/CSV), fuzzy-fix row off-by-one, mixed-format inversion, empty-input scored-100 bug, unified multi-file score, full `cli.py` coverage, Excel custom-rule names, plus nice-to-have polish. Three refactors to single sources: `score_band()`, `issue_headline()`, `count_sheet_issues()`. Rebased onto the diverged remote (kept its 1.1.5 + realistic sample), regenerated both sample sets, released **1.2.0 to PyPI**, added `review.yaml`, fixed CHANGELOG links, deleted backup branch.

**State:** `main` synced with origin (`010cc7d`), 262 tests / ruff / mypy green, **1.2.0 live on PyPI**, tree clean. Two unrelated `claude/*` local branches untouched.

**Next:** Nothing outstanding — project stable at 1.2.0. Optional: clean up the `claude/*` local branches. Run `git fetch` first next session (remote may move from other machines).

## 2026-07-24 17:04

**Started from:** `main` on `5a49fb4` (gitleaks postgres rule + credential redaction), CI green. A harness-managed worktree needed teardown.

**Did:** Deregistered the `isolation: worktree` worktree (`recursing-saha-feebe6`) from git — `git worktree list` shows only the main checkout. Deleted merged local branch `ci-actions-node24` (remote already gone). No code changes.

**State:** `main` on `5a49fb4`, tree clean, ahead of `origin/main` by 1 unpushed commit. Branches `audit-fixes-2026-07` (ahead of remote by 1) and `claude/recursing-saha-feebe6` left untouched. CI green. The physical folder `.claude/worktrees/recursing-saha-feebe6` self-cleans when this session closes (Windows file lock while session runs inside it).

**Next:** Push `main` to origin (1 commit not backed up). Decide fate of `audit-fixes-2026-07` and `claude/recursing-saha-feebe6` — merge, keep, or delete.
