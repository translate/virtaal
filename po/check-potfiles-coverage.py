#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Replaces intltool-update --maintain's whole-tree scan (used by
    po/check-pot-freshness.sh) - gettext's own tools have no equivalent
    of it. Finds every .py file with a real _()/N_()/ngettext()/C_()
    call (an ast.Call, not a string match - a variable or comment that
    merely contains "_(" doesn't count) and reports any not listed in
    po/POTFILES.in or po/POTFILES.skip: its strings would otherwise
    never be extracted for translation at all, silently.

    Prints one repo-relative path per line for each uncovered file and
    exits 1 if any are found; exits 0 (silently) otherwise.

    Scope matches the intltool-update --maintain-based check this
    replaces: .py files only. .ui/.glade files (translatable="yes"
    attributes, not function calls) were never covered by that check
    either - a real but separate gap, not attempted here."""

import ast
import sys
from pathlib import Path

TRANSLATABLE_CALLS = {'_', 'N_', 'ngettext', 'C_'}

# Generated/vendored/environment trees - never real project source.
IGNORE_DIR_PREFIXES = ('.venv', 'build', 'dist', '.git', 'devsupport/pseudo-translation')


def has_translatable_call(path):
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in TRANSLATABLE_CALLS:
            return True
    return False


def read_list(path):
    entries = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('['):
            entries.add(line)
    return entries


def main():
    repo_root = Path(__file__).resolve().parent.parent
    covered = read_list(repo_root / 'po' / 'POTFILES.in') | read_list(repo_root / 'po' / 'POTFILES.skip')

    missing = []
    for path in sorted(repo_root.rglob('*.py')):
        rel = path.relative_to(repo_root).as_posix()
        if rel.startswith(IGNORE_DIR_PREFIXES) or rel in covered:
            continue
        if has_translatable_call(path):
            missing.append(rel)

    if missing:
        print('\n'.join(missing))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
