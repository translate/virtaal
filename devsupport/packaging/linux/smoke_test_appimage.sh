#!/bin/bash
# Runs a built AppImage on this machine and checks it works:
#   smoke_test_appimage.sh Virtaal-linux-<arch>.AppImage
# Needs a display (or xvfb-run), the libraries every desktop has that the
# AppImage leaves out (libxcb, the Wayland client libraries, fontconfig),
# and the host's en_US hunspell dictionary (hunspell-en-us on
# Debian/Ubuntu, hunspell-en-US on Fedora): the AppImage uses the host's
# installed dictionaries. And pgrep. With HUNSPELL_HU_DIR set to a
# directory with hu_HU.aff and hu_HU.dic, also checks Hungarian.
set -eu -o pipefail

APPIMAGE="$(realpath "$1")"
LOGS="$(mktemp -d)"
trap 'rm -rf "$LOGS"' EXIT
# Containers have no FUSE. Each run reuses the first run's extraction,
# which goes in $LOGS so it's removed at the end.
export APPIMAGE_EXTRACT_AND_RUN=1 NO_CLEANUP=1 TMPDIR="$LOGS/tmp"
mkdir "$TMPDIR"

LAUNCH=("$APPIMAGE")
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    LAUNCH=(xvfb-run -a --server-args="-screen 0 1024x768x24" "$APPIMAGE")
fi
# The first run also extracts the AppImage.
run() {
    timeout -k 5 120 "${LAUNCH[@]}" "$@"
}
stage() {
    echo "== $* (${SECONDS}s)"
}

stage "version, with the build's commit"
run --version | tee "$LOGS/version.txt"
if grep -q "(unknown)" "$LOGS/version.txt"; then
    echo "The build's commit isn't recorded" >&2
    exit 1
fi

stage "msgfmt check library"
run --run-module virtaal.support.gettextpo | tee "$LOGS/gettextpo.txt"
grep -q "^library: /.*/libgettextpo.so.0$" "$LOGS/gettextpo.txt"

stage "bundled translations"
LANGUAGE=de run --help | tee "$LOGS/help.txt"
grep -q "Fehleranalysefeatures aktivieren" "$LOGS/help.txt"

stage "spell checking, with the host's dictionary"
run --run-module virtaal.support.enchant_compat en_US | tee "$LOGS/enchant.txt"
grep -q "^enchant: /.*/enchant/lib/libenchant-2.so.2$" "$LOGS/enchant.txt"
grep -q "^providers: .*hunspell" "$LOGS/enchant.txt"
grep -q "^dictionary: True$" "$LOGS/enchant.txt"
grep -q "^gtkspell: ok$" "$LOGS/enchant.txt"
grep -q "^marked: tset$" "$LOGS/enchant.txt"
grep -qx "foreign: *" "$LOGS/enchant.txt"
grep -qx "duplicates: *" "$LOGS/enchant.txt"

if [ -n "${HUNSPELL_HU_DIR:-}" ]; then
    stage "spell checking Hungarian"
    mkdir -p "$LOGS/enchant-hu/hunspell"
    cp "$HUNSPELL_HU_DIR/hu_HU.aff" "$HUNSPELL_HU_DIR/hu_HU.dic" "$LOGS/enchant-hu/hunspell"
    ENCHANT_CONFIG_DIR="$LOGS/enchant-hu" run --run-module virtaal.support.enchant_compat hu_HU | tee "$LOGS/enchant-hu.txt"
    grep -q "^dictionary: True$" "$LOGS/enchant-hu.txt"
    grep -q "^gtkspell: ok$" "$LOGS/enchant-hu.txt"
    grep -q "^marked: xqzwy$" "$LOGS/enchant-hu.txt"
fi

stage "the desktop's settings, not the build machine's"
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

stage "the bundled icons of every stock item, at 16 and 32 pixels"
# GTK draws a stock item (gtk-open) with the theme's full-colour icon
# (document-open), named in GTK 3's gtkiconfactory.c. Every stock item
# in virtaal.ui must be listed.
cat > "$LOGS/stock_icons.py" <<'EOF'
import os
import re
import sys
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from virtaal.common import pan_app
ICONS = {
    "gtk-about": "help-about", "gtk-add": "list-add", "gtk-cancel": "gtk-cancel",
    "gtk-close": "window-close", "gtk-copy": "edit-copy", "gtk-cut": "edit-cut",
    "gtk-go-down": "go-down", "gtk-go-up": "go-up", "gtk-missing-image": "image-missing",
    "gtk-ok": "gtk-ok", "gtk-open": "document-open", "gtk-paste": "edit-paste",
    "gtk-preferences": "gtk-preferences", "gtk-properties": "document-properties",
    "gtk-quit": "application-exit", "gtk-refresh": "view-refresh", "gtk-remove": "list-remove",
    "gtk-save": "document-save", "gtk-save-as": "document-save-as", "gtk-undo": "edit-undo",
}
with open(pan_app.get_abs_data_filename(["virtaal", "virtaal.ui"]), encoding="utf-8") as f:
    used = sorted(set(re.findall(r">(gtk-[a-z-]+)<", f.read())))
# The bundle's Adwaita only, not the host's (and GTK's built-in icons).
theme = Gtk.IconTheme()
theme.set_search_path([os.path.join(sys._MEIPASS, "share", "icons")])
theme.set_custom_theme("Adwaita")
style = Gtk.Image().get_style_context()
for stock in used:
    name = ICONS.get(stock)
    if name is None:
        print("unlisted stock item: " + stock)
        continue
    for size, scale in ((16, 1), (32, 1), (16, 2)):
        info = theme.lookup_icon_for_scale(name, size, scale, 0)
        print("%s %s %d@%d: %s" % (stock, name, size, scale, info.get_filename() if info else "missing"))
    # As a menu item does: warns if the icon doesn't load.
    for scale in (1, 2):
        Gtk.IconFactory.lookup_default(stock).render_icon_surface(style, Gtk.IconSize.MENU, scale, None)
print("stock icons checked: %d" % len(used))
EOF
echo "exec(open('$LOGS/stock_icons.py').read())" | run --run-module code > "$LOGS/stock-icons.txt" 2>&1 || true
cat "$LOGS/stock-icons.txt"
if ! grep -q "^stock icons checked: [1-9]" "$LOGS/stock-icons.txt" \
        || grep -E ": missing$|^unlisted stock item|Error loading theme icon|Traceback" "$LOGS/stock-icons.txt"; then
    echo "A stock item's icon isn't bundled" >&2
    exit 1
fi

stage "IBus's input method module under Wayland, unless the user chose one"
probe='import os; print("im=" + os.environ.get("GTK_IM_MODULE", "none"))'
im="$(echo "$probe" | WAYLAND_DISPLAY=smoke-test XMODIFIERS=@im=ibus timeout -k 5 60 "$APPIMAGE" --run-module code 2>&1 | grep -o 'im=[a-z0-9]*')"
chosen="$(echo "$probe" | WAYLAND_DISPLAY=smoke-test XMODIFIERS=@im=ibus GTK_IM_MODULE=fcitx timeout -k 5 60 "$APPIMAGE" --run-module code 2>&1 | grep -o 'im=[a-z0-9]*')"
echo "$im, with fcitx chosen: $chosen"
[ "$im" = im=ibus ] && [ "$chosen" = im=fcitx ]

stage "a browser gets the host's libraries, not the bundle's"
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

stage "a file opens, with a bundled input method"
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
entry="$LOGS/home/.local/share/applications/virtaal-appimage.desktop"
if ! grep -qx "TryExec=$APPIMAGE" "$entry"; then
    echo "No menu entry for the AppImage" >&2
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
