#!/bin/bash
# Builds dist/Virtaal.dmg: a real, drag-to-Applications installer wrapping
# dist/Virtaal.app (build_standalone.sh's self-contained bundle - build
# that first, this doesn't do it for you).
#
# Uses dmgbuild (pure Python, no Finder AppleScript automation needed -
# more reliable in CI than create-dmg's shell+osascript approach).
# Layout/assets in devsupport/packaging/macos/dmgbuild-settings.py,
# reusing devsupport/mac-bundle/virtaal_DMG_background.png and
# icons/VolumeIcon_virtaal.icns.
set -eu
cd "$(git rev-parse --show-toplevel)"

PYTHON="$PWD/.venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="python3"

[ -d dist/Virtaal.app ] || {
  echo "dist/Virtaal.app not found - run build_standalone.sh first." >&2
  exit 1
}

"$PYTHON" -m pip show dmgbuild >/dev/null 2>&1 || "$PYTHON" -m pip install dmgbuild

rm -f dist/Virtaal.dmg
"$PYTHON" -m dmgbuild --settings devsupport/packaging/macos/dmgbuild-settings.py \
  --detach-retries 30 \
  "Virtaal" dist/Virtaal.dmg

echo "Built dist/Virtaal.dmg"
