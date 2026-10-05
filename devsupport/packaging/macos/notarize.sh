#!/bin/bash
# Notarizes and staples a signed Virtaal.app or .dmg:
#   notarize.sh dist/Virtaal.app
#   notarize.sh dist/Virtaal.dmg
#
# Authenticates with an App Store Connect API key rather than an Apple
# ID, so there's no password or 2FA prompt: $APPLE_API_KEY_PATH (the
# AuthKey_<id>.p8 file), $APPLE_API_KEY_ID and $APPLE_API_ISSUER_ID.
#
# notarytool only accepts a zip, dmg or pkg - an .app is zipped with
# ditto for the upload, and the ticket stapled to the .app itself.
set -euo pipefail

target="$1"
[ -e "$target" ] || {
  echo "$target not found." >&2
  exit 1
}

auth=(--key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID")

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

upload="$target"
if [ -d "$target" ]; then
  upload="$workdir/$(basename "$target").zip"
  ditto -c -k --sequesterRsrc --keepParent "$target" "$upload"
fi

# notarytool exits 0 for a finished-but-rejected ("Invalid") submission,
# so check the status rather than the exit code.
xcrun notarytool submit "$upload" "${auth[@]}" --wait --timeout 15m \
  --output-format json > "$workdir/result.json"
id="$(plutil -extract id raw "$workdir/result.json")"
status="$(plutil -extract status raw "$workdir/result.json")"
echo "Notarization $id: $status"

if [ "$status" != Accepted ]; then
  xcrun notarytool log "$id" "${auth[@]}"
  exit 1
fi

xcrun stapler staple "$target"
xcrun stapler validate "$target"
