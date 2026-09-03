#!/bin/bash
# Pre-commit hook: warn if an icon .svg source changed without its
# .icns being regenerated to match, via build_icons.sh. pre-commit
# itself only invokes this when a relevant .svg is among the changed
# files (see the `files:` pattern in .pre-commit-config.yaml) - unlike
# po/check-pot-freshness.sh, whose relevant-file set is dynamic
# (whatever po/POTFILES.in currently lists) and so can't be expressed
# as a fixed pattern, this hook's two source files are fixed, so
# pre-commit's own filtering covers it without any filtering here.
#
# Only covers VirtaalDocument.icns and icons/VolumeIcon_virtaal.icns -
# what build_icons.sh itself builds. virtaal_DMG_background.svg has no
# equivalent regeneration script yet (it produces a .png, not a .icns,
# via a different, not-yet-automated path) - not checked here.
#
# Requires rsvg-convert (librsvg) and iconutil (Xcode Command Line
# Tools, macOS-only) - degrades to a note, not a failure, if either is
# missing. Unlike po/check-pot-freshness.sh, nothing in CI currently
# rebuilds these either, so this is a local-only safety net for now,
# not backstopped elsewhere.
set -eu
cd "$(git rev-parse --show-toplevel)"

for tool in rsvg-convert iconutil; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "NOTE: an icon .svg source changed, but $tool isn't installed" >&2
        echo "here to check whether the .icns needs regenerating - see" >&2
        echo "devsupport/mac-bundle/build_icons.sh." >&2
        exit 0
    fi
done

before_doc=$(git hash-object devsupport/mac-bundle/VirtaalDocument.icns)
before_vol=$(git hash-object devsupport/mac-bundle/icons/VolumeIcon_virtaal.icns)

devsupport/mac-bundle/build_icons.sh >/dev/null

after_doc=$(git hash-object devsupport/mac-bundle/VirtaalDocument.icns)
after_vol=$(git hash-object devsupport/mac-bundle/icons/VolumeIcon_virtaal.icns)

if [ "$before_doc" = "$after_doc" ] && [ "$before_vol" = "$after_vol" ]; then
    exit 0
fi

echo "An icon .svg source changed and its .icns is now stale relative to it." >&2
echo "build_icons.sh just regenerated it (already written to disk) - review" >&2
echo "the diff and 'git add' the result, or 'git checkout' it back if this" >&2
echo "diff is unrelated to what you're committing." >&2
exit 1
