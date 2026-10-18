#!/bin/bash
# Builds build/appimage/Virtaal-linux-<arch>.AppImage: a PyInstaller
# bundle of Virtaal, Python, GTK and the spell checker, packed with
# appimagetool. Run it on Ubuntu 22.04 (its glibc is the oldest the
# AppImage runs on), with these packages installed:
#
#   python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0
#   gir1.2-gtkspell3-3.0 libgettextpo0 gettext gcc g++ make pkg-config
#   libglib2.0-dev libhunspell-dev librsvg2-common adwaita-icon-theme
#   ibus-gtk3 fcitx5-frontend-gtk3 desktop-file-utils file curl
#
# PyInstaller imports virtaal's modules, which start GTK: without a
# display, run it under xvfb-run.
set -eu
cd "$(dirname "$0")/../../.."

PYINSTALLER_VERSION=6.22.3  # keep in step with ci.yml's Windows build
APPIMAGETOOL_VERSION=1.9.1
RUNTIME_VERSION=20251108
ENCHANT_VERSION=2.3.2  # Ubuntu 22.04's
ENCHANT_SHA256=ce9ba47fd4d34031bd69445598a698a6611602b2b0e91d705e91a6f5099ead6e

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)
        APPIMAGETOOL_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
        RUNTIME_SHA256=2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d
        ;;
    aarch64)
        APPIMAGETOOL_SHA256=f0837e7448a0c1e4e650a93bb3e85802546e60654ef287576f46c71c126a9158
        RUNTIME_SHA256=00cbdfcf917cc6c0ff6d3347d59e0ca1f7f45a6df1a428a0d6d8a78664d87444
        ;;
    *)
        echo "Unsupported architecture: $ARCH" >&2
        exit 1
        ;;
esac

OUT="$PWD/build/appimage"
rm -rf "$OUT/dist" "$OUT/work" "$OUT/Virtaal.AppDir"
mkdir -p "$OUT/tools"

fetch() {  # url sha256 dest
    if ! echo "$2  $3" | sha256sum -c --status 2>/dev/null; then
        curl -fsSL --retry 5 --retry-all-errors --connect-timeout 30 --max-time 300 -o "$3" "$1"
        echo "$2  $3" | sha256sum -c --quiet
    fi
}
fetch "https://github.com/AppImage/appimagetool/releases/download/$APPIMAGETOOL_VERSION/appimagetool-$ARCH.AppImage" \
    "$APPIMAGETOOL_SHA256" "$OUT/tools/appimagetool-$ARCH.AppImage"
fetch "https://github.com/AppImage/type2-runtime/releases/download/$RUNTIME_VERSION/runtime-$ARCH" \
    "$RUNTIME_SHA256" "$OUT/tools/runtime-$ARCH"
chmod +x "$OUT/tools/appimagetool-$ARCH.AppImage"
fetch "https://github.com/AbiWord/enchant/releases/download/v$ENCHANT_VERSION/enchant-$ENCHANT_VERSION.tar.gz" \
    "$ENCHANT_SHA256" "$OUT/tools/enchant-$ENCHANT_VERSION.tar.gz"

# enchant, built relocatable: Ubuntu's always looks for its providers in
# /usr/lib, so it would never find the bundled ones. Only the hunspell
# provider. gtkspell3 links this one, as PyInstaller resolves it first.
rm -rf "$OUT/enchant-src" "$OUT/enchant"
mkdir -p "$OUT/enchant-src"
tar xzf "$OUT/tools/enchant-$ENCHANT_VERSION.tar.gz" -C "$OUT/enchant-src" --strip-components=1
(
    cd "$OUT/enchant-src"
    CFLAGS="-O2 -w" CXXFLAGS="-O2 -w" ./configure -q --prefix=/opt/virtaal-enchant --enable-relocatable --disable-static \
        --with-hunspell --without-nuspell --without-aspell --without-hspell --without-voikko
    make -s -j"$(nproc)"
    make -s install DESTDIR="$OUT/enchant"
)
export VIRTAAL_ENCHANT_PREFIX="$OUT/enchant/opt/virtaal-enchant"

# A fresh venv with only Ubuntu's PyGObject and pycairo linked in, as
# the macOS build does - PyInstaller bundles whatever an import trace
# reaches (#3871).
VENV="$PWD/build/appimage-venv"
rm -rf "$VENV"
/usr/bin/python3 -m venv "$VENV"
PYTHON="$VENV/bin/python3"
/usr/bin/python3 - "$("$PYTHON" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" <<'EOF'
import glob, os, sys
import cairo, gi
for mod, dist in ((gi, "PyGObject"), (cairo, "pycairo")):
    site = os.path.dirname(mod.__path__[0])
    for src in [mod.__path__[0], *glob.glob(os.path.join(site, dist + "-*-info"))]:
        os.symlink(src, os.path.join(sys.argv[1], os.path.basename(src)))
EOF
"$PYTHON" -m pip install -q setuptools==84.0.0 wheel==0.48.0 \
    "pyinstaller==$PYINSTALLER_VERSION" translate-toolkit
"$PYTHON" -m pip install -q --no-build-isolation ".[spellcheck]"
"$PYTHON" devsupport/packaging/macos/check_build_venv.py

./maketranslations
"$PYTHON" setup.py --version >/dev/null

# The commit the About dialog and bug reports show. CI passes the PR's
# real head (see the macOS build_standalone.sh).
commit="${VIRTAAL_BUILD_COMMIT:-$(git rev-parse HEAD)}"
echo "commit = \"$commit\"" > virtaal/_build_info.py
echo "Building from commit $commit"

LD_LIBRARY_PATH="$VIRTAAL_ENCHANT_PREFIX/lib" "$PYTHON" -m PyInstaller -y --distpath "$OUT/dist" --workpath "$OUT/work" \
    devsupport/packaging/linux/virtaal.spec

APPDIR="$OUT/Virtaal.AppDir"
mv "$OUT/dist/virtaal" "$APPDIR"
# A script, not a link: GTK names the app after the executable it was
# started as.
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
exec "$(dirname "$(readlink -f "$0")")/Virtaal" "$@"
EOF
chmod +x "$APPDIR/AppRun"
# pyenchant takes enchant's prefix from the library's path; see
# pyi_rth_appimage.py. A link, so only one copy of the library loads.
mkdir -p "$APPDIR/enchant/lib"
ln -s ../../libenchant-2.so.2 "$APPDIR/enchant/lib/libenchant-2.so.2"
test -e "$APPDIR/enchant/lib/libenchant-2.so.2"

# Not on PATH: the AppImage is run by its own path.
grep -v '^TryExec=' share/applications/io.github.translate.Virtaal.desktop \
    > "$APPDIR/io.github.translate.Virtaal.desktop"
desktop-file-validate "$APPDIR/io.github.translate.Virtaal.desktop"
cp share/icons/hicolor/256x256/apps/io.github.translate.Virtaal.png "$APPDIR/"
ln -s io.github.translate.Virtaal.png "$APPDIR/.DirIcon"
install -Dm644 share/metainfo/io.github.translate.Virtaal.metainfo.xml \
    "$APPDIR/usr/share/metainfo/io.github.translate.Virtaal.appdata.xml"

# appimagetool is itself an AppImage; extract-and-run needs no FUSE.
export ARCH
APPIMAGE_EXTRACT_AND_RUN=1 "$OUT/tools/appimagetool-$ARCH.AppImage" \
    --no-appstream --runtime-file "$OUT/tools/runtime-$ARCH" \
    "$APPDIR" "$OUT/Virtaal-linux-$ARCH.AppImage"
echo "Built $OUT/Virtaal-linux-$ARCH.AppImage"
