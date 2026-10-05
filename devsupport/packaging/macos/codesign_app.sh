#!/bin/bash
# Signs dist/Virtaal.app inside-out with the hardened runtime: every
# Mach-O file, then each nested .framework, then the app itself with
# entitlements.plist. Run after build_standalone.sh - its
# Contents/MacOS/share symlink is added after PyInstaller has already
# sealed the bundle, so PyInstaller's own signature is never valid.
#
# $CODESIGN_IDENTITY is the "Developer ID Application: ..." identity to
# sign with. Unset, the bundle is signed ad-hoc ("-") - same layout and
# entitlements, so the hardened runtime is still exercised, but it can't
# be notarized.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

APP=dist/Virtaal.app
IDENTITY="${CODESIGN_IDENTITY:--}"
ENTITLEMENTS=devsupport/packaging/macos/entitlements.plist

[ -d "$APP" ] || {
  echo "$APP not found - run build_standalone.sh first." >&2
  exit 1
}

sign() {
  codesign --sign "$IDENTITY" --force --timestamp --options runtime "$@"
}

# --mime-type rather than parsing file's free-text description: some
# bundled files' descriptions aren't valid UTF-8, which aborts awk/grep.
find "$APP/Contents" -type f -print0 | while IFS= read -r -d '' path; do
  if [ "$(file -b --mime-type "$path")" = application/x-mach-binary ]; then
    sign "$path"
  fi
done

find "$APP/Contents" -type d -name '*.framework' | while IFS= read -r framework; do
  sign "$framework"
done

sign --entitlements "$ENTITLEMENTS" "$APP"

codesign --verify --deep --strict --verbose=2 "$APP"
echo "Signed $APP as: $IDENTITY"
