#!/bin/bash
# Builds dist/Virtaal.dmg: a real, drag-to-Applications installer wrapping
# dist/Virtaal.app (build_standalone.sh's self-contained bundle - build
# that first, this doesn't do it for you).
#
# Uses dmgbuild (pure Python, no Finder AppleScript automation needed -
# more reliable in CI than create-dmg's shell+osascript approach).
# Layout/assets in devsupport/packaging/macos/dmgbuild-settings.py,
# reusing devsupport/mac-bundle/virtaal_DMG_background{,@2x}.png and
# icons/VolumeIcon_virtaal.icns.
set -eu
cd "$(git rev-parse --show-toplevel)"

PYTHON="$PWD/.venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="python3"

[ -d dist/Virtaal.app ] || {
  echo "dist/Virtaal.app not found - run build_standalone.sh first." >&2
  exit 1
}

"$PYTHON" -m pip install -q dmgbuild==1.6.7

rm -f dist/Virtaal.dmg
"$PYTHON" -m dmgbuild --settings devsupport/packaging/macos/dmgbuild-settings.py \
  --detach-retries 30 \
  "Virtaal" dist/Virtaal.dmg

# Unsigned (ad-hoc) builds leave the .dmg itself unsigned - an ad-hoc
# signature on a disk image means nothing to Gatekeeper.
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  codesign --sign "$CODESIGN_IDENTITY" --timestamp dist/Virtaal.dmg
  codesign --verify --verbose=2 dist/Virtaal.dmg
fi

echo "Built dist/Virtaal.dmg"
