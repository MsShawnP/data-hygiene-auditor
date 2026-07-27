# FAILURES

What didn't work and why, so we don't repeat it. Most recent on top.

## 2026-07-27 — `python -m data_hygiene_auditor.cli` does nothing

**Tags:** cli, tooling

Running the package via `python -m data_hygiene_auditor.cli` imports the
module but never calls `main()` — there's no `if __name__ == '__main__'`
guard and no `__main__.py`. Also the CLI takes `--input`/`--output`
(output is a *directory*), not a positional path or `--format`. To drive
it in a script/test, call `data_hygiene_auditor.cli.main()` directly after
setting `sys.argv`, or use the installed `data-hygiene-audit` console
script.

## 2026-07-27 — review.yaml strict-loader pitfalls

**Tags:** ui-review, config

The `ui-review-skill` loader rejects `path: ""` (each route needs a
truthy path) — for a single static file, put the directory in `base_url`
and the filename in the route `path`. Also the default dev-marker pattern
`TODO|FIXME|HACK|XXX` fires false positives here because the reports embed
`(XXX) XXX-XXXX` phone masks; dropped `XXX` from the pattern.

## 2026-07-27 — the messy sample has no standalone fuzzy duplicates

**Tags:** tests, detection

De-brittling `test_includes_fuzzy_duplicates` into a hard assert revealed
that `sample_messy_data.xlsx` produces **zero** fuzzy duplicates — all its
near-duplicates are caught first as *phantom* duplicates (case/whitespace/
punctuation), and the fuzzy detector skips groups already covered by a
phantom group. The old `if has_fuzzy:` guard had been passing vacuously.
Fix: test `count_issues` with a synthetic fuzzy entry instead of assuming
the sample contains one.
