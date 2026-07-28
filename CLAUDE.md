
## Serif display sizes — documented deviation

`data_hygiene_auditor/reporting/html.py` sizes its serif display type in `rem`
against a 16px root, so the steps land near the Lailara type scale without
hitting it:

| Selector | Size | Computed | Nearest DS token | Status |
|---|---|---|---|---|
| `h1` | 1.8rem | 28.8px | Benchmark value 28px | **Deviation** (rem scale) |
| `h2` | 1.4rem | 22.4px | Section title 22px | **Deviation** (rem scale) |
| `h3` | 1.1rem | 17.6px | Section title mobile 18px | **Deviation** (rem scale) |
| `.summary-card .number` | 2rem | 32px | Benchmark value 28px | **Deviation.** Hero counts; 28px collapses them into the card labels. |
| `.score-meta .score-label`, `.trend-banner .delta` | 1.3rem | 20.8px | none | **Deviation.** Sits in the DS "card / sub-section head" 18–20 band. |

This is a whole-file rem scale, not a handful of stray literals. Converting it
to px tokens is a typography pass on the generated report, not a find-replace —
the rem base also drives spacing and the report has no mobile step block.

The frame's `.ll-*` display classes are not available here: this generator emits
a self-contained HTML file and does not vendor `lailara-frame.css`.

Do not "fix" these to tokens mechanically.
