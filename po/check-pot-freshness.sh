#!/bin/bash
# Pre-commit hook, two checks:
# 1. Fail if any source file has gettext markers but isn't listed in
#    po/POTFILES.in or po/POTFILES.skip - its strings would otherwise
#    never be extracted for translation at all.
# 2. Warn if a file that feeds po/virtaal.pot (see po/POTFILES.in)
#    changed without po/virtaal.pot being regenerated to match.
#
# `make pot` runs `po/update-pot` (xgettext), which stamps a fresh
# `POT-Creation-Date` header every single run regardless of content -
# verified the hard way, by trusting an initial same-minute test that
# happened not to show it. That line is stripped out before comparing,
# so only real content changes trip this.
#
# `#:` location comments are filename-only (po/update-pot passes
# xgettext --add-location=file), so unrelated line-number shifts
# elsewhere in a file no longer touch them at all. They're still
# ignored here by default, belt-and-braces, since a string moving to a
# different file entirely is still possible - it has no effect on what
# translators actually see either way. Set POT_STRICT_LOCATIONS=1 to
# also require these be current.
set -eu
cd "$(git rev-parse --show-toplevel)"

changed=("$@")
[ "${#changed[@]}" -eq 0 ] && exit 0

# A file with gettext markers that isn't in po/POTFILES.in at all
# wouldn't be caught by the staleness check below (which only looks at
# files POTFILES.in already lists) - it'd just be silently missing
# from translation, forever (confirmed the hard way: crash_dialog.py
# sat in neither POTFILES.in nor POTFILES.skip for a whole port cycle
# before this check existed). po/check-potfiles-coverage.py is the
# whole-repo check for this - real ast-based call detection, not a
# grep heuristic, and it already respects POTFILES.skip - so an entry
# it flags is a hard fail, not just a note.
# .ui/.glade files aren't checked here (translatable="yes" attributes,
# not _()/N_()/ngettext() calls - a different check, not implemented).
coverage_output=$(python3 po/check-potfiles-coverage.py) || {
    echo "File(s) have gettext markers (_()/N_()/ngettext()/C_()) but aren't listed in po/POTFILES.in or po/POTFILES.skip - their strings won't be extracted for translation:" >&2
    echo "  ${coverage_output//$'\n'/$'\n'  }" >&2
    echo "Add them to po/POTFILES.in (or po/POTFILES.skip if deliberately excluded)." >&2
    exit 1
}

relevant=false
for f in "${changed[@]}"; do
    # po/POTFILES.in itself governs what `make pot` extracts - editing
    # it (adding/removing entries) is exactly as relevant as editing
    # one of the files it lists, but it doesn't list itself.
    # virtaal/__version__.py isn't in POTFILES.in either (no
    # translatable strings) but po/update-pot reads it directly for
    # xgettext's --package-version, so a version bump alone still
    # makes the pot's header stale.
    if [ "$f" = "po/POTFILES.in" ] || [ "$f" = "virtaal/__version__.py" ]; then
        relevant=true
    fi
done
while IFS= read -r potfile; do
    case "$potfile" in
        \[*|"") continue ;;
    esac
    for f in "${changed[@]}"; do
        if [ "$f" = "$potfile" ]; then
            relevant=true
        fi
    done
done < po/POTFILES.in

if [ "$relevant" = false ]; then
    exit 0
fi

# Explicit check for entries pointing at files that no longer exist -
# this is exactly the bug that motivated this hook (po/POTFILES.in
# still listed three plugins removed in an earlier commit, silently
# breaking `make pot` for everything after). Reported here, upfront
# and by name, rather than relying on `make pot`/xgettext below: it
# stops at the *first* missing file it hits and its error is easy to
# miss among xgettext's own routine warnings.
missing=()
while IFS= read -r potfile; do
    case "$potfile" in
        \[*|"") continue ;;
    esac
    [ -f "$potfile" ] || missing+=("$potfile")
done < po/POTFILES.in
if [ "${#missing[@]}" -gt 0 ]; then
    echo "po/POTFILES.in lists file(s) that no longer exist on disk:" >&2
    printf '  %s\n' "${missing[@]}" >&2
    echo "Remove the stale entries (or restore the files, if that was unintentional)." >&2
    exit 1
fi

filter_relevant() {
    local filtered
    # --no-wrap first: different xgettext versions (e.g. Homebrew vs.
    # apt's gettext-tools) wrap long msgid/msgstr lines at different
    # widths - confirmed the hard way, a real false-positive here on
    # otherwise byte-identical content. One line per string sidesteps
    # that entirely, regardless of which version generated the file.
    filtered=$(msgcat --no-wrap "$1" | grep -v '^"POT-Creation-Date:')
    if [ "${POT_STRICT_LOCATIONS:-}" != "1" ]; then
        filtered=$(printf '%s\n' "$filtered" | grep -v '^#:')
    fi
    printf '%s\n' "$filtered"
}

hash_relevant() {
    filter_relevant "$1" | git hash-object --stdin
}

original_backup=$(mktemp)
trap 'rm -f "$original_backup"' EXIT
cp po/virtaal.pot "$original_backup"

before=$(hash_relevant po/virtaal.pot)

if ! make_output=$(make pot 2>&1); then
    echo "'make pot' itself failed (not just stale - couldn't regenerate at all):" >&2
    echo "$make_output" >&2
    exit 1
fi
after=$(hash_relevant po/virtaal.pot)

if [ "$before" = "$after" ]; then
    # Nothing relevant changed - just the POT-Creation-Date timestamp
    # (make pot stamps a fresh one every run, unconditionally) and/or
    # location comments (ignored unless POT_STRICT_LOCATIONS=1, see
    # above). Restore the exact original bytes (not just
    # content-equivalent - a command substitution round-trip would
    # silently normalize trailing newlines) so this hook doesn't leave
    # a spurious diff behind on an otherwise-clean pass. pre-commit
    # treats *any* file changing during a hook's run as reportable,
    # regardless of the hook's own exit code - confirmed the hard way,
    # this used to fail every relevant commit even when nothing was
    # actually stale.
    cp "$original_backup" po/virtaal.pot
else
    echo "po/virtaal.pot is now stale relative to your changes." >&2
    echo "'make pot' just regenerated it (already written to disk) - review the diff and 'git add po/virtaal.pot', or 'git checkout po/virtaal.pot' if this diff is unrelated to what you're committing." >&2
    echo >&2
    diff -u <(filter_relevant "$original_backup") <(filter_relevant po/virtaal.pot) >&2 || true
    exit 1
fi
