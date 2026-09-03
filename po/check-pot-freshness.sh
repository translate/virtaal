#!/bin/bash
# Pre-commit hook: warn if a file that feeds po/virtaal.pot (see
# po/POTFILES.in) changed without po/virtaal.pot being regenerated to
# match. `make pot` runs `po/intltool-update --pot`, which stamps a
# fresh `POT-Creation-Date` header every single run regardless of
# content - verified the hard way, by trusting an initial same-minute
# test that happened not to show it. That line is stripped out before
# comparing, so only real content changes trip this.
#
# `#:` location comments (source file:line references) are also
# ignored by default - they drift on their own as unrelated code
# elsewhere shifts line numbers, with no effect on what translators
# actually see, so routine commits shouldn't have to regenerate the
# whole file just to keep them current. Set POT_STRICT_LOCATIONS=1 to
# also require these be current - the real check to run before a
# release, where accurate source references matter.
#
# Requires `intltool-update` on PATH (`brew install intltool` /
# `apt install intltool`). Not everyone doing a routine commit will have
# it installed - this degrades to a note, not a failure, in that case;
# CI's docs-and-translations job always has it and is the real backstop.
set -eu
cd "$(git rev-parse --show-toplevel)"

changed=("$@")
[ "${#changed[@]}" -eq 0 ] && exit 0

# Separate, non-blocking check: a *new* .py file with gettext markers
# that isn't in po/POTFILES.in at all wouldn't be caught by the
# staleness check below (which only looks at files POTFILES.in already
# lists) - it'd just be silently missing from translation, forever.
# Note rather than fail: grep-based detection has real false-positive
# risk (e.g. an unrelated variable literally named `_`), and this is a
# "did you forget" nudge, not an invariant like staleness is.
# .ui/.glade files aren't checked here (translatable="yes" attributes,
# not _()/N_()/ngettext() calls - a different check, not implemented).
for f in "${changed[@]}"; do
    case "$f" in
        *.py) ;;
        *) continue ;;
    esac
    [ -f "$f" ] || continue
    case "$f" in
        devsupport/*|*/_*|_*) continue ;;  # debug-only plugins, dev tooling - see plugincontroller.py's `name[0] != '_'`
    esac
    if grep -qE '\b(_|N_|ngettext)\(' "$f" && ! grep -qxF "$f" po/POTFILES.in; then
        echo "NOTE: $f has gettext markers (_()/N_()/ngettext()) but isn't listed in po/POTFILES.in - its strings won't be extracted for translation. Add it there if that's not intentional." >&2
    fi
done

relevant=false
for f in "${changed[@]}"; do
    # po/POTFILES.in itself governs what `make pot` extracts - editing
    # it (adding/removing entries) is exactly as relevant as editing
    # one of the files it lists, but it doesn't list itself.
    if [ "$f" = "po/POTFILES.in" ]; then
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

if ! command -v intltool-update >/dev/null 2>&1; then
    echo "NOTE: a file listed in po/POTFILES.in changed, but intltool-update" >&2
    echo "isn't installed here to check whether po/virtaal.pot needs" >&2
    echo "regenerating (brew install intltool / apt install intltool)." >&2
    echo "CI's docs-and-translations job will still catch it if this is missed." >&2
    exit 0
fi

# Explicit check for entries pointing at files that no longer exist -
# this is exactly the bug that motivated this hook (po/POTFILES.in
# still listed three plugins removed in an earlier commit, silently
# breaking `make pot` for everything after). Reported here, upfront
# and by name, rather than relying on `make pot`/xgettext below: it
# stops at the *first* missing file it hits and its error is easy to
# miss among the routine intltool-update Perl warnings.
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

hash_relevant() {
    local filtered
    filtered=$(grep -v '^"POT-Creation-Date:' "$1")
    if [ "${POT_STRICT_LOCATIONS:-}" != "1" ]; then
        filtered=$(printf '%s\n' "$filtered" | grep -v '^#:')
    fi
    printf '%s\n' "$filtered" | git hash-object --stdin
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
    exit 1
fi
