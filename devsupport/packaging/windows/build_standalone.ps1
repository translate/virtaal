# Builds dist\virtaal\virtaal.exe as a real, self-contained bundle: Python,
# GTK3/PyGObject's DLLs, and every dependency vendored inside dist\virtaal\
# via PyInstaller - runs on a machine that never had this checkout or a
# gvsbuild GTK3 install set up at all, unlike just running `python
# bin\virtaal` from a checkout (see .github/workflows/ci.yml's
# test-windows job for that whole toolchain).
#
# PyInstaller's Windows --onedir output is flat (everything next to
# virtaal.exe), matching translate-toolkit's own frozen-mode data
# lookup assumption exactly (confirmed by reading the installed package:
# os.path.dirname(sys.executable), not a split-directory layout).
#
# Run from the repo root, in a shell that already has the gvsbuild/MSVC
# environment set up (same PKG_CONFIG_PATH/GI_TYPELIB_PATH/INCLUDE/LIB/
# PATH as CONTRIBUTING.md's local-testing section and ci.yml's
# test-windows job) - this only builds the frozen bundle, it doesn't set
# up the build environment itself.

$ErrorActionPreference = "Stop"

$RepoRoot = (git rev-parse --show-toplevel)
Set-Location $RepoRoot

$Python = "python"

# setup.py's mo-compile step runs unconditionally as a side effect of
# *any* setup.py invocation (see setup.py's own module docstring) - this
# is the documented way to trigger it without going through pip/build.
& $Python setup.py --version | Out-Null

$pyinstallerInstalled = & $Python -m pip show pyinstaller 2>$null
if (-not $pyinstallerInstalled) {
    & $Python -m pip install pyinstaller
}

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build\virtaal, dist\virtaal

# See virtaal/__version__.py's build_commit docstring: a frozen build has
# no .git directory or git binary to ask "which commit is this", so write
# the answer down now, while both are still available, for
# virtaal.exe --version (and anything scripted checking it, e.g.
# devsupport/testing/windows's Install-Virtaal) to read back later. Not
# checked into git (see .gitignore) - virtaal.spec's own
# sys.path.insert(0, ROOT) (repo root first) means this local-tree file
# wins over any installed site-packages copy of virtaal when
# collect_submodules("virtaal") picks it up below.
#
# $env:VIRTAAL_BUILD_COMMIT lets CI override this: `git rev-parse HEAD`
# on a pull_request-triggered runner is GitHub's own ephemeral
# preview-merge commit, not the branch's real head - fetchable nowhere,
# so useless for a human comparing a downloaded build against their own
# checkout. CI passes the real head SHA explicitly instead.
if ($env:VIRTAAL_BUILD_COMMIT) {
    $commit = $env:VIRTAAL_BUILD_COMMIT
} else {
    $commit = (git rev-parse HEAD).Trim()
}
"commit = `"$commit`"" | Set-Content -Path virtaal\_build_info.py -Encoding utf8
Write-Host "Building from commit $commit"

& $Python -m PyInstaller -y devsupport\packaging\windows\virtaal.spec

Write-Host "Built dist\virtaal\virtaal.exe (self-contained)"
