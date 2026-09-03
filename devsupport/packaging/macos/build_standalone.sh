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

rm -rf build/virtaal dist/Virtaal.app

# See virtaal/__version__.py's build_commit docstring: a frozen build has
# no .git directory or git binary to ask "which commit is this", so write
# the answer down now, while both are still available, for
# Virtaal.app --version (and anything scripted checking it) to read back
# later. Not checked into git (see .gitignore) - virtaal.spec's own
# sys.path.insert(0, ROOT) (repo root first) means this local-tree file
# wins over any installed site-packages copy of virtaal when
# collect_submodules("virtaal") picks it up below.
commit="$(git rev-parse HEAD)"
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
