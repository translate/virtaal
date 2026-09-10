#!/bin/bash
# Pre-commit hook: every .py file should carry the unified header
# documented in .license.header.txt. Tolerates an optional shebang
# line immediately above the block (only setup.py actually needs
# one - see PR #3430), doesn't require its absence.
#
# Skips a small, fixed allowlist of files that deliberately don't
# carry this header - either a genuine third-party notice sits above
# it instead (locale.py, openmailto.py, sorted_set.py,
# simplegeneric.py all still append it underneath their own, so they
# pass), the file is wholesale vendored code with no Virtaal copyright
# to state at all (ipython_view.py, selector.py, statsdb.py, tmdb.py,
# tmserver.py, translate_compat.py, wsgi.py), or its own descriptive
# comment starts with a bare "#" too, tripping the heuristic below
# (docs/conf.py).
#
# Doesn't touch files that never had a header at all before this
# check existed (a real, separate,
# not-yet-made decision) - only checks files that already do.
set -eu

HEADER='#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.'

ALLOWLIST='
docs/conf.py
virtaal/support/libi18n/locale.py
virtaal/support/openmailto.py
virtaal/support/sorted_set.py
virtaal/support/simplegeneric.py
virtaal/plugins/_ipython_console/ipython_view.py
virtaal/support/selector.py
virtaal/support/statsdb.py
virtaal/support/tmdb.py
virtaal/support/tmserver.py
virtaal/support/translate_compat.py
virtaal/support/wsgi.py
'

changed=("$@")
failed=()

for f in "${changed[@]}"; do
    case "$f" in
        *.py) ;;
        *) continue ;;
    esac
    [ -f "$f" ] || continue
    case "$ALLOWLIST" in
        *$'\n'"$f"$'\n'*) continue ;;
    esac

    # A file that never had a header before this check existed isn't
    # this check's problem to fix - only files that already carry
    # *some* header are held to the unified text.
    if ! head -1 "$f" | grep -qE '^#(!/usr/bin/env python.*)?$'; then
        continue
    fi

    actual=$(sed -n '1,6p' "$f")
    if [ "${actual#\#!/usr/bin/env python}" != "$actual" ]; then
        # Shebang present - the header starts one line later.
        actual=$(sed -n '2,7p' "$f")
    fi

    if [ "$actual" != "$HEADER" ]; then
        failed+=("$f")
    fi
done

if [ "${#failed[@]}" -gt 0 ]; then
    echo "These files don't carry the unified copyright header (see .license.header.txt):" >&2
    printf '  %s\n' "${failed[@]}" >&2
    exit 1
fi
