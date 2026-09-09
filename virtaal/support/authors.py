#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Reads AUTHORS.md so the About dialog's contributor list comes from
the same single source everyone else (GitHub, Pootle-style
convention) reads, instead of a separately hand-maintained copy that
inevitably drifts.

AUTHORS.md deliberately stays a real top-level file (not under
share/), so it doesn't go through pan_app.get_abs_data_filename()'s
share/-only resolution - it needs its own, here."""

import os
import sys


def find_authors_md():
    """The real AUTHORS.md path, in a dev checkout or a frozen build
        (bundled at the bundle root - see devsupport/packaging/*/
        virtaal.spec's datas), or None if it can't be found."""
    candidates = []
    if getattr(sys, 'frozen', False):
        # RESOURCEPATH: same env var translate-toolkit's own
        # file_discovery.get_abs_data_filename() checks for a macOS
        # .app bundle's Contents/Resources - PyInstaller's BUNDLE step
        # doesn't put root-level datas next to the executable there,
        # unlike a Windows/Linux onedir build.
        if 'RESOURCEPATH' in os.environ:
            candidates.append(os.path.join(os.environ['RESOURCEPATH'], 'AUTHORS.md'))
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'AUTHORS.md'))
    else:
        # This file lives at virtaal/support/authors.py - the repo
        # root is two directories up.
        candidates.append(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            os.pardir, os.pardir, 'AUTHORS.md'))
    for candidate in candidates:
        candidate = os.path.normpath(candidate)
        if os.path.isfile(candidate):
            return candidate
    return None


def parse_contributors(path):
    """Returns the list of names from AUTHORS.md's "## Contributors"
        section, or an empty list if the file doesn't have one.

        Donor/funder names aren't parsed here deliberately - those are
        a handful of already-translated, stable strings (see
        AboutDialog), kept as real literal _() calls in source rather
        than round-tripped through this file's exact wording."""
    contributors = []
    in_section = False
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('## '):
                in_section = line[3:].strip() == 'Contributors'
                continue
            if in_section and line.startswith('- '):
                contributors.append(line[2:].strip())
    return contributors
