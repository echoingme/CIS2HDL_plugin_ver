#!/usr/bin/env bash
# CIS2HDL v2c — re-run HG5015 conversion for QA comparison.
#
# Converts the HG5015 reference design into HG5015_tests/output_v2c
# using the same HDL library that produced output_v2b, so the two
# outputs can be diffed directly (match strategy distribution, conf
# distribution, NEEDS_REVIEW count, HTML report rendering).
#
# Usage:
#   bash scripts/run_hg5015_v2c.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON_BIN:-C:/Users/echo/.workbuddy/binaries/python/versions/3.13.12/python.exe}"

if [ ! -f "$PY" ]; then
    PY="$ROOT/.venv/Scripts/python.exe"
fi

DSN="$ROOT/tests/fixtures/HG5015test/HG5015-BE36_V10.DSN"
OUT="$ROOT/HG5015_tests/output_v2c"
HDL_LIB="$ROOT/HG5015_tests/output_v2b/hdl_lib"

echo "== CIS2HDL v2c HG5015 conversion =="
echo "python : $PY"
echo "dsn    : $DSN"
echo "output : $OUT"
echo "hdl_lib: $HDL_LIB"
echo

cd "$ROOT"
PYTHONPATH="$ROOT" "$PY" -m cis2hdl convert \
    "$DSN" \
    --output "$OUT" \
    --hdl-lib "$HDL_LIB"

echo
echo "== Done. Output written to: $OUT =="
