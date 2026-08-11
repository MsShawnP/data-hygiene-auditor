#!/usr/bin/env bash
# Regenerate the committed samples/output/ deliverables reproducibly.
#
# SOURCE_DATE_EPOCH pins the report generation timestamp (see DECISIONS.md,
# 2026-08-07) so the .html and .pdf outputs are byte-identical run-to-run.
# The value below is 2026-08-05 00:00:00 UTC — the 1.3.0 release date. Keep it
# stable so anyone regenerating gets the same bytes; bump it only on a release.
#
# Note: the .xlsx findings file is content-reproducible but NOT byte-lockable —
# openpyxl stamps wall-clock times into the workbook envelope. See DECISIONS.md.
set -euo pipefail
cd "$(dirname "$0")/.."

export SOURCE_DATE_EPOCH=1785888000  # 2026-08-05 00:00:00 UTC (1.3.0)

python audit.py -i samples/input/sample_messy_data.xlsx     -o samples/output/
python audit.py -i samples/input/sample_realistic_data.xlsx -o samples/output/

echo "Regenerated samples/output/ with SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH"
