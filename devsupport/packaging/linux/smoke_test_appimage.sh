#!/bin/bash
# Runs a built AppImage on this machine and checks it works:
#   smoke_test_appimage.sh Virtaal-linux-<arch>.AppImage
# Needs a display (or xvfb-run), the libraries every desktop has that the
# AppImage leaves out (libxcb, the Wayland client libraries, fontconfig),
# and the host's en_US hunspell dictionary (hunspell-en-us on
# Debian/Ubuntu, hunspell-en-US on Fedora): the AppImage uses the host's
# installed dictionaries. And pgrep.
set -eu -o pipefail

APPIMAGE="$(realpath "$1")"
# Containers have no FUSE.
export APPIMAGE_EXTRACT_AND_RUN=1
LOGS="$(mktemp -d)"
trap 'rm -rf "$LOGS"' EXIT

LAUNCH=("$APPIMAGE")
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    LAUNCH=(xvfb-run -a --server-args="-screen 0 1024x768x24" "$APPIMAGE")
fi
run() {
    "${LAUNCH[@]}" "$@"
}

echo "== version, with the build's commit"
run --version | tee "$LOGS/version.txt"
if grep -q "(unknown)" "$LOGS/version.txt"; then
    echo "The build's commit isn't recorded" >&2
    exit 1
fi

echo "== msgfmt check library"
run --run-module virtaal.support.gettextpo | tee "$LOGS/gettextpo.txt"
grep -q "^library: /.*/libgettextpo.so.0$" "$LOGS/gettextpo.txt"

echo "== bundled translations"
LANGUAGE=de run --help | tee "$LOGS/help.txt"
grep -q "Fehleranalysefeatures aktivieren" "$LOGS/help.txt"

echo "== spell checking, with the host's dictionary"
run --run-module virtaal.support.enchant_compat en_US | tee "$LOGS/enchant.txt"
grep -q "^enchant: /.*/enchant/lib/libenchant-2.so.2$" "$LOGS/enchant.txt"
grep -q "^providers: .*hunspell" "$LOGS/enchant.txt"
grep -q "^dictionary: True$" "$LOGS/enchant.txt"
grep -q "^gtkspell: ok$" "$LOGS/enchant.txt"

echo "== the desktop's settings, not the build machine's"
if command -v gsettings >/dev/null; then
    host="$(gsettings get org.gnome.desktop.interface icon-theme | tr -d "'")"
    echo 'from gi.repository import Gio; print("icon-theme=" + Gio.Settings.new("org.gnome.desktop.interface").get_string("icon-theme"))' \
        | run --run-module code > "$LOGS/gsettings.txt" 2>&1 || true
    bundle="$(grep -o 'icon-theme=.*' "$LOGS/gsettings.txt" | cut -d= -f2)"
    echo "icon theme: $host, in the AppImage: $bundle"
    if [ "$host" != "$bundle" ]; then
        cat "$LOGS/gsettings.txt"
        echo "The AppImage doesn't see the desktop's GSettings defaults" >&2
        exit 1
    fi
fi

echo "== IBus's input method module under Wayland, unless the user chose one"
probe='import os; print("im=" + os.environ.get("GTK_IM_MODULE", "none"))'
im="$(echo "$probe" | WAYLAND_DISPLAY=smoke-test XMODIFIERS=@im=ibus "$APPIMAGE" --run-module code 2>&1 | grep -o 'im=[a-z0-9]*')"
chosen="$(echo "$probe" | WAYLAND_DISPLAY=smoke-test XMODIFIERS=@im=ibus GTK_IM_MODULE=fcitx "$APPIMAGE" --run-module code 2>&1 | grep -o 'im=[a-z0-9]*')"
echo "$im, with fcitx chosen: $chosen"
[ "$im" = im=ibus ] && [ "$chosen" = im=fcitx ]

echo "== a browser gets the host's libraries, not the bundle's"
mkdir -p "$LOGS/bin"
printf '#!/bin/sh\nenv > "%s"\n' "$LOGS/xdg-open-env.txt" > "$LOGS/bin/xdg-open"
chmod +x "$LOGS/bin/xdg-open"
# Its exit status is inverted (sys.exit(True) on success).
PATH="$LOGS/bin:$PATH" run --run-module virtaal.support.openmailto https://example.org/ || true
test -s "$LOGS/xdg-open-env.txt"
if grep -E "^(LD_LIBRARY_PATH|GI_TYPELIB_PATH|GTK_PATH|GTK_IM_MODULE_FILE|GDK_PIXBUF_MODULE_FILE|_PYI_)|appimage_extracted|/tmp/\.mount_" "$LOGS/xdg-open-env.txt"; then
    echo "xdg-open got the bundle's environment" >&2
    exit 1
fi

echo "== a file opens, with a bundled input method"
# A fresh home: no earlier config. Stopped after 20 seconds. XIM needs
# no input method server to load.
mkdir -p "$LOGS/home"
printf 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\nmsgid "Hello"\nmsgstr ""\n' > "$LOGS/test.po"
status=0
HOME="$LOGS/home" XDG_CONFIG_HOME="$LOGS/home/.config" GTK_IM_MODULE=xim \
    timeout -k 5 -s INT 20 "${LAUNCH[@]}" --debug "$LOGS/test.po" > "$LOGS/run.txt" 2>&1 &
launcher=$!
sleep 15
pid="$(pgrep -f "/Virtaal --debug $LOGS/test.po" | head -1 || true)"
modules="$( (grep -o 'immodules/im-[a-z0-9-]*\.so' "/proc/$pid/maps" 2>/dev/null || true) | sort -u)"
wait "$launcher" || status=$?
cat "$LOGS/run.txt"
if [ "$status" != 124 ]; then
    echo "The app exited (status $status) instead of still running after 20 seconds" >&2
    exit 1
fi
echo "Input method modules loaded: $modules"
if [ "$modules" != "immodules/im-xim.so" ]; then
    echo "The bundled XIM input method module wasn't loaded" >&2
    exit 1
fi
if grep -E "Traceback|CRITICAL|Segmentation fault|cannot open shared object" "$LOGS/run.txt"; then
    echo "The app reported an error" >&2
    exit 1
fi
echo "AppImage smoke test passed"
