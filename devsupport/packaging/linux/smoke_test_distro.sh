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
case "$ID" in
    ubuntu|debian)
        export DEBIAN_FRONTEND=noninteractive
        # dnf retries a stalled download by default; apt needs telling.
        printf "%s\n" "Acquire::Retries \"3\";" "Acquire::http::Timeout \"30\";" \
            "Acquire::https::Timeout \"30\";" > /etc/apt/apt.conf.d/80retries
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
echo "== packages installed (${SECONDS}s)"
/test/smoke_test_appimage.sh /test/Virtaal.AppImage
'
