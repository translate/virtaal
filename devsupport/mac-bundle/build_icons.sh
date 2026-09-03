#!/bin/bash
# Rebuilds VirtaalDocument.icns and icons/VolumeIcon_virtaal.icns from
# the Inkscape .svg sources in this directory - run this after editing
# the SVGs, not by hand. macOS-only: iconutil (packs a folder of PNGs
# at fixed sizes into a real .icns) ships with Xcode Command Line
# Tools; rsvg-convert (rasterizes the SVGs) is librsvg, e.g.
# `brew install librsvg`.
#
# VirtaalDocumentIcon_32x32x32.svg is rendered for the 16/32px tier,
# VirtaalDocumentIcon_512x512x32.svg for 128px and up - two separate
# source files, not one scaled, so small sizes can carry simplified
# detail that would look muddy rendered down from the full-detail
# artwork.
set -eu
cd "$(dirname "$0")"

for tool in rsvg-convert iconutil; do
  command -v "$tool" >/dev/null || {
    echo "build_icons.sh needs $tool - see this script's header." >&2
    exit 1
  }
done

build_icns() {
  local name="$1" small="$2" large="$3"
  local iconset="/tmp/${name}.iconset"
  rm -rf "$iconset"
  mkdir -p "$iconset"

  rsvg-convert -w 16 -h 16 "$small" -o "$iconset/icon_16x16.png"
  rsvg-convert -w 32 -h 32 "$small" -o "$iconset/icon_16x16@2x.png"
  rsvg-convert -w 32 -h 32 "$small" -o "$iconset/icon_32x32.png"
  rsvg-convert -w 64 -h 64 "$large" -o "$iconset/icon_32x32@2x.png"
  rsvg-convert -w 128 -h 128 "$large" -o "$iconset/icon_128x128.png"
  rsvg-convert -w 256 -h 256 "$large" -o "$iconset/icon_128x128@2x.png"
  rsvg-convert -w 256 -h 256 "$large" -o "$iconset/icon_256x256.png"
  rsvg-convert -w 512 -h 512 "$large" -o "$iconset/icon_256x256@2x.png"
  rsvg-convert -w 512 -h 512 "$large" -o "$iconset/icon_512x512.png"
  rsvg-convert -w 1024 -h 1024 "$large" -o "$iconset/icon_512x512@2x.png"

  iconutil -c icns "$iconset" -o "${name}.icns"
  rm -rf "$iconset"
  echo "Built ${name}.icns"
}

build_icns VirtaalDocument VirtaalDocumentIcon_32x32x32.svg VirtaalDocumentIcon_512x512x32.svg
build_icns icons/VolumeIcon_virtaal icons/VolumeIcon_virtaal.svg icons/VolumeIcon_virtaal.svg
