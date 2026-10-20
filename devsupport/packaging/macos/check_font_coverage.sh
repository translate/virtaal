#!/bin/bash
# Checks that every shipped interface language displays in a built
# Virtaal.app's fonts (#4421):
#   check_font_coverage.sh dist/Virtaal.app [--strict]
#
# Fails on a gap not in KNOWN_GAPS (virtaal/support/fontcoverage.py).
# A known gap that displays now is a warning, or with --strict (the
# weekly run) a failure, so its entry is removed once fixed.
set -euo pipefail

app=$1
strict=${2:-}
out=$(mktemp)
"$app/Contents/MacOS/virtaal" --run-module virtaal.support.fontcoverage "$out"
cat "$out"
grep "displays now" "$out" | sed 's/^/::warning::/' || true
if ! grep -q "^new: 0$" "$out"; then
    echo "::error::Characters with no glyph, not in KNOWN_GAPS; see above"
    exit 1
fi
if [ "$strict" = --strict ] && grep -q "displays now" "$out"; then
    echo "::error::Known gaps display now; remove them from KNOWN_GAPS"
    exit 1
fi
