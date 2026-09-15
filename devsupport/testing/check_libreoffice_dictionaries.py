#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Validate every LibreOffice dictionaries repo folder still resolves to
real, fetchable .aff/.dic files - run periodically (see
.github/workflows/check-libreoffice-dictionaries.yml) so an upstream
repo restructuring is caught before a user's spell-check download
silently fails.

Walks every folder from list_dictionary_folders() directly, not through
find_dictionary()'s locale-guessing layer - this checks the whole repo,
not one app-side lookup."""

import sys
import urllib.request
from urllib.error import HTTPError, URLError

from virtaal.support.dictionary_source import (
    dictionary_file_url_candidates,
    fetch_dictionary_tree,
    fetch_xcu,
    list_dictionary_folders,
    parse_dictionaries_xcu,
)


def _file_exists(folder, filename):
    for url in dictionary_file_url_candidates(folder, filename):
        request = urllib.request.Request(url, method='HEAD')
        try:
            urllib.request.urlopen(request, timeout=10)
            return True
        except (HTTPError, URLError):
            continue
    return False


def check_folder(folder):
    """Every problem found for one folder, as a list of strings (empty
    if it's fine)."""
    try:
        entries = parse_dictionaries_xcu(fetch_xcu(folder))
    except Exception as e:
        return ['%s: could not parse dictionaries.xcu (%s)' % (folder, e)]
    if not entries:
        return ['%s: dictionaries.xcu has no HunSpellDic_* entries' % folder]
    problems = []
    for entry in entries:
        for filename in entry['files']:
            if not _file_exists(folder, filename):
                problems.append('%s/%s: not found' % (folder, filename))
    return problems


def main():
    tree = fetch_dictionary_tree()
    folders = list_dictionary_folders(tree)
    failures = []
    for folder in sorted(folders):
        failures.extend(check_folder(folder))

    if failures:
        print('%d problem(s) found:' % len(failures))
        for f in failures:
            print(' -', f)
        return 1
    print('All %d dictionary folders resolve cleanly.' % len(folders))
    return 0


if __name__ == '__main__':
    sys.exit(main())
