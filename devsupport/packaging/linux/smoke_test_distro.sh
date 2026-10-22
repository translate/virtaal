#!/bin/bash
# Runs smoke_test_appimage.sh in a bare distribution image, with only
# what every desktop has installed (no GTK, no Python):
#   smoke_test_distro.sh IMAGE APPIMAGE
# e.g. smoke_test_distro.sh fedora:44 build/appimage/Virtaal-linux-x86_64.AppImage
set -eu

IMAGE="$1"
APPIMAGE="$(realpath "$2")"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "== pulling $IMAGE"
pull() {
    if command -v timeout >/dev/null; then
        timeout 120 docker pull -q "$IMAGE"
    else
        docker pull -q "$IMAGE"
    fi
}
for attempt in 1 2 3; do
    pull && break
    [ "$attempt" = 3 ] && exit 1
done
echo "== pulled (${SECONDS}s)"

docker run --rm --init \
    -v "$APPIMAGE:/test/Virtaal.AppImage:ro" \
    -v "$HERE/smoke_test_appimage.sh:/test/smoke_test_appimage.sh:ro" \
    "$IMAGE" bash -c '
set -eu
. /etc/os-release
echo "== installing packages"
# A stalled mirror can hold apt or dnf for good: retry it.
fetch() {
    for attempt in 1 2 3; do
        timeout 180 "$@" >/dev/null && return
        echo "== $1 $2 failed (${SECONDS}s)"
    done
    return 1
}
case "$ID" in
    ubuntu|debian)
        export DEBIAN_FRONTEND=noninteractive
        printf "%s\n" "Acquire::Retries \"3\";" "Acquire::http::Timeout \"30\";" \
            "Acquire::https::Timeout \"30\";" > /etc/apt/apt.conf.d/80retries
        packages="xvfb xauth hunspell-en-us libxcb1 libwayland-client0 libwayland-egl1
            libwayland-cursor0 libfontconfig1 procps gsettings-desktop-schemas libglib2.0-bin"
        # Ubuntu sets its desktop defaults (the Yaru theme) as schema
        # overrides for its own desktop.
        if [ "$ID" = ubuntu ]; then
            packages="$packages ubuntu-settings"
            export XDG_CURRENT_DESKTOP=ubuntu:GNOME
        fi
        fetch apt-get update -qq
        echo "== updated (${SECONDS}s)"
        fetch apt-get install -y -qq --no-install-recommends --download-only $packages
        echo "== downloaded (${SECONDS}s)"
        apt-get install -y -qq --no-install-recommends $packages >/dev/null
        ;;
    fedora)
        packages="xorg-x11-server-Xvfb xvfb-run xauth hunspell-en-US libxcb libwayland-client
            libwayland-egl libwayland-cursor fontconfig procps-ng gsettings-desktop-schemas glib2"
        fetch dnf makecache -q
        echo "== updated (${SECONDS}s)"
        fetch dnf install -y -q --downloadonly $packages
        echo "== downloaded (${SECONDS}s)"
        dnf install -y -q $packages >/dev/null
        ;;
    *)
        echo "No package list for $ID" >&2
        exit 1
        ;;
esac
echo "== packages installed (${SECONDS}s)"
/test/smoke_test_appimage.sh /test/Virtaal.AppImage
'
