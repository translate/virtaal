#!/bin/bash
# Runs smoke_test_appimage.sh in a bare distribution image, with only
# what every desktop has installed (no GTK, no Python):
#   smoke_test_distro.sh IMAGE APPIMAGE
# e.g. smoke_test_distro.sh fedora:44 build/appimage/Virtaal-linux-x86_64.AppImage
set -eu

IMAGE="$1"
APPIMAGE="$(realpath "$2")"
HERE="$(cd "$(dirname "$0")" && pwd)"

docker run --rm \
    -v "$APPIMAGE:/test/Virtaal.AppImage:ro" \
    -v "$HERE/smoke_test_appimage.sh:/test/smoke_test_appimage.sh:ro" \
    "$IMAGE" bash -c '
set -eu
. /etc/os-release
case "$ID" in
    ubuntu|debian)
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq >/dev/null
        apt-get install -y -qq --no-install-recommends xvfb xauth hunspell-en-us \
            libxcb1 libwayland-client0 libwayland-egl1 libwayland-cursor0 libfontconfig1 procps \
            gsettings-desktop-schemas libglib2.0-bin >/dev/null
        # Ubuntu sets its desktop defaults (the Yaru theme) as schema
        # overrides for its own desktop.
        if [ "$ID" = ubuntu ]; then
            apt-get install -y -qq --no-install-recommends ubuntu-settings >/dev/null
            export XDG_CURRENT_DESKTOP=ubuntu:GNOME
        fi
        ;;
    fedora)
        dnf install -y -q xorg-x11-server-Xvfb xvfb-run xauth hunspell-en-US \
            libxcb libwayland-client libwayland-egl libwayland-cursor fontconfig procps-ng \
            gsettings-desktop-schemas glib2 >/dev/null
        ;;
    *)
        echo "No package list for $ID" >&2
        exit 1
        ;;
esac
/test/smoke_test_appimage.sh /test/Virtaal.AppImage
'
