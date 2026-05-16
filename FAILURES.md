# Failures Log

Things that didn't work and why, so we don't repeat them.

---

## 2026-05-16: PyPI trusted publisher — case sensitivity mismatch

**What happened:** Configured the PyPI trusted publisher with "Data-Hygiene-Auditor" (mixed case matching the GitHub repo display name). The `publish.yml` workflow failed with an OIDC claim mismatch.

**Root cause:** GitHub OIDC tokens always send the repository name lowercase (`data-hygiene-auditor`), regardless of how the repo is displayed in the UI. PyPI does a case-sensitive match.

**Fix:** Deleted and re-created the pending publisher on PyPI with lowercase repo name and explicit `pypi` environment name (not "Any").

**Lesson:** When configuring PyPI trusted publishing, always use lowercase for the repository name. Also set the environment field explicitly — don't leave it as "(Any)".

**Tags:** #pypi #ci #oidc #github-actions

---

## 2026-05-16: Fuzzy test failure — synthetic unique names classified as IDs

**What happened:** Test for 600-row fuzzy matching generated names like "Person0", "Person1"... and injected a typo pair at rows 100/200. Test assertion failed — no Levenshtein matches found.

**Root cause:** Every "Person{i}" name was unique → the detection engine's `infer_field_type()` classified the Name column as an ID column (high cardinality, unique values) → ID columns are excluded from fuzzy matching → the injected typo pair was never compared.

**Fix:** Rewrote test data to use realistic pools of repeated first/last names, making the Name column look like a name column rather than an ID column.

**Lesson:** When writing test data for detection engines, the data must be realistic enough to pass upstream classification. Synthetic sequential patterns (incrementing suffixes) trigger ID classification. Use pools of realistic values with natural repetition.

**Tags:** #testing #fuzzy-matching #field-classification

---

## 2026-05-16: Rebase conflicts after GitHub squash merge

**What happened:** After squash-merging a PR on GitHub, tried to rebase the local branch. Got conflicts in CHANGELOG.md and other files.

**Root cause:** GitHub squash merge creates a single new commit on main that contains all the PR's changes, but the local branch still has the original individual commits. When rebasing onto the updated main, git sees the squashed commit and the original commits as conflicting changes to the same lines.

**Fix:** Resolved manually by keeping the correct content during rebase, or used `git push --force-with-lease` when the local branch was the source of truth.

**Lesson:** After squash-merging on GitHub, don't rebase the same local commits. Either: (1) delete the local branch and re-branch from updated main, or (2) if continuing work, `git reset --soft` to main and recommit, or (3) accept that force-push will be needed for the next PR branch.

**Tags:** #git #squash-merge #rebase #workflow
