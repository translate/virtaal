#!/bin/bash
# Builds dist/Virtaal.app as a real, self-contained bundle: Python, GTK3/
# PyGObject's dylibs, and every dependency vendored inside Contents/ via
# PyInstaller - unlike build.sh's dist/Virtaal.app, this one runs on a
# machine that never had this checkout, Homebrew, or GTK3 set up at all.
#
# This is deliberately a separate script from build.sh, not a replacement
# for it: build.sh is fast (no build step, just wraps this checkout's
# .venv) and useful for quick local iteration; this one is slow
# (PyInstaller has to trace and copy the whole dependency tree) and is
# the one that actually matters for distribution. This also fixes the
# "Python" branding limitation build.sh's bundle still has: PyInstaller
# produces a compiled native bootloader that embeds the interpreter
# directly, never invoking a Framework Python's own launcher, so the
# self-relaunch-into-Resources/Python.app mechanism that blocks the
# launcher-script approach never gets a chance to fire.
set -eu
cd "$(git rev-parse --show-toplevel)"

PYTHON="$PWD/.venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="python3"

# setup.py's mo-compile step runs unconditionally as a side effect of
# *any* setup.py invocation (see setup.py's own module docstring) - this
# is the documented way to trigger it without going through pip/build.
"$PYTHON" setup.py --version >/dev/null

"$PYTHON" -m pip show pyinstaller >/dev/null 2>&1 || "$PYTHON" -m pip install pyinstaller

# pyenchant stopped shipping self-contained macOS wheels after 2.0.0 -
# that one is an Intel-only universal (i386+x86_64) bundle of
# libenchant 1.x + myspell backend + a few dictionaries, its exports
# matching what modern pyenchant's _enchant.py calls. No arm64 build
# exists, so this step - and virtaal.spec's use of its output - is a
# no-op there. Only the native bits are staged here; virtaal.spec
# still bundles *current* pyenchant's own Python code, pointed at this
# dylib via PYENCHANT_LIBRARY_PATH/ENCHANT_MODULE_DIR/ENCHANT_DATA_DIR
# (pan_app.py sets these, frozen+Intel only).
rm -rf build/enchant_intel
if [ "$(uname -m)" = "x86_64" ]; then
    curl -sL -o /tmp/pyenchant-2.0.0-mac.whl \
        "https://files.pythonhosted.org/packages/4f/c5/5c18df3c5dbf2ce1e6fc8b0fcce1a5dfe7c4ec5ab33b76722fcca9cbfff5/pyenchant-2.0.0-py2.py3.cp27.cp32.cp33.cp34.cp35.cp36.pp27.pp33.pp35-none-macosx_10_6_intel.macosx_10_9_intel.whl"
    mkdir -p build/enchant_intel
    # en_US (traditional software source language) and en_GB (checks.po's
    # own target language) - everything else comes via download
    # (dictionary_source.py), not bundled.
    unzip -q /tmp/pyenchant-2.0.0-mac.whl 'enchant/lib/*' \
        'enchant/share/enchant/myspell/en_US.aff' \
        'enchant/share/enchant/myspell/en_US.dic' \
        'enchant/share/enchant/myspell/en_GB.aff' \
        'enchant/share/enchant/myspell/en_GB.dic' \
        -d build/enchant_intel
    rm /tmp/pyenchant-2.0.0-mac.whl
fi

rm -rf build/virtaal dist/Virtaal.app

# See virtaal/__version__.py's build_commit docstring: a frozen build has
# no .git directory or git binary to ask "which commit is this", so write
# the answer down now, while both are still available, for
# Virtaal.app --version (and anything scripted checking it) to read back
# later. Not checked into git (see .gitignore) - virtaal.spec's own
# sys.path.insert(0, ROOT) (repo root first) means this local-tree file
# wins over any installed site-packages copy of virtaal when
# collect_submodules("virtaal") picks it up below.
#
# $VIRTAAL_BUILD_COMMIT lets CI override this: `git rev-parse HEAD` on
# a pull_request-triggered runner is GitHub's own ephemeral
# preview-merge commit, not the branch's real head - fetchable nowhere,
# so useless for a human comparing a downloaded build against their own
# checkout. CI passes the real head SHA explicitly instead.
commit="${VIRTAAL_BUILD_COMMIT:-$(git rev-parse HEAD)}"
echo "commit = \"$commit\"" > virtaal/_build_info.py
echo "Building from commit $commit"

"$PYTHON" -m PyInstaller -y devsupport/packaging/macos/virtaal.spec

# PyInstaller's macOS BUNDLE step relocates data files (share/) into
# Contents/Resources/ (proper Apple convention), but translate-toolkit's
# frozen-mode data lookup (file_discovery.py) only checks next to the
# executable (Contents/MacOS/) - a Windows/PyInstaller-flat-layout
# assumption that doesn't hold for a macOS .app's split layout. A
# symlink is the fix, not patching an external dependency.
ln -sf ../Resources/share dist/Virtaal.app/Contents/MacOS/share

echo "Built dist/Virtaal.app (self-contained)"
