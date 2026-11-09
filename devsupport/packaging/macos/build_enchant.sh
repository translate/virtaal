#!/bin/bash
# Builds enchant with its hunspell provider, for the self-contained .app
# (Homebrew's enchant has aspell and AppleSpell only):
#   build_enchant.sh OUT
# Installs to OUT/opt/virtaal-enchant; skipped when OUT already has this
# build. Needs Homebrew's glib, hunspell, pkg-config and groff.
set -eu

OUT="$1"
ENCHANT_VERSION=2.8.21
ENCHANT_SHA256=dd2a762697c463148a8f59867089a5ebf2dd1449d869f93764b76c12bcf8acc0
PATCH="$(cd "$(dirname "$0")" && pwd)/enchant-library-spelling.patch"
PREFIX=/opt/virtaal-enchant
STAMP="$OUT/built-from"
want="$ENCHANT_SHA256 $(shasum -a 256 "$PATCH" | cut -c1-64) $(brew list --versions glib hunspell | tr '\n' ' ')"

if [ "$(cat "$STAMP" 2>/dev/null)" = "$want" ]; then
    echo "enchant $ENCHANT_VERSION already built in $OUT"
    exit 0
fi

rm -rf "$OUT"
mkdir -p "$OUT/src"
curl -fsSL --retry 5 --retry-all-errors --connect-timeout 30 --max-time 300 \
    -o "$OUT/enchant.tar.gz" \
    "https://github.com/rrthomas/enchant/releases/download/v$ENCHANT_VERSION/enchant-$ENCHANT_VERSION.tar.gz"
echo "$ENCHANT_SHA256  $OUT/enchant.tar.gz" | shasum -a 256 -c -
tar xzf "$OUT/enchant.tar.gz" -C "$OUT/src" --strip-components=1
(
    cd "$OUT/src"
    patch -p1 < "$PATCH"
    PKG_CONFIG_PATH="$(brew --prefix hunspell)/lib/pkgconfig:$(brew --prefix glib)/lib/pkgconfig" \
        CFLAGS="-O2 -w" CXXFLAGS="-O2 -w" OBJCXXFLAGS="-O2 -w" \
        ./configure -q --prefix="$PREFIX" --enable-relocatable --disable-static \
        --with-hunspell --without-applespell --without-aspell --without-nuspell \
        --without-hspell --without-voikko --without-zemberek
    make -s -j"$(sysctl -n hw.ncpu)"
    make -s install DESTDIR="$OUT"
)
rm -rf "$OUT/src" "$OUT/enchant.tar.gz"

# The library and providers name the install prefix, which doesn't
# exist; PyInstaller finds them by these paths.
LIB="$OUT$PREFIX/lib"
install_name_tool -id "$LIB/libenchant-2.2.dylib" "$LIB/libenchant-2.2.dylib"
for provider in "$LIB"/enchant-2/*.so; do
    install_name_tool -change "$PREFIX/lib/libenchant-2.2.dylib" "$LIB/libenchant-2.2.dylib" "$provider"
done
otool -L "$LIB/libenchant-2.2.dylib" "$LIB"/enchant-2/*.so
echo "$want" > "$STAMP"
