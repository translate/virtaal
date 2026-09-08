#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Source autocorrect data directly from LibreOffice's own core repo
(github.com/LibreOffice/core, extras/source/autocorr/lang) - just the
DocumentList.xml virtaal/plugins/autocorrector.py's AutoCorrector
actually reads, not LibreOffice's zip packaging around it (the zip's
other members have never been read by this codebase).

Simpler than dictionary_source.py's shape in one real way: a folder
always covers exactly one locale here (no dictionaries.xcu-equivalent
listing several locales per file to parse and match against), so
resolving locale_code to its folder is candidate_folders() alone,
reused unchanged - once a candidate folder is known to exist, there's
nothing left to verify against its content.

Deliberately NOT the recursive git-trees call dictionary_source.py
uses to enumerate LibreOffice/dictionaries: LibreOffice/core is the
project's full monorepo, too large for a repo-wide recursive call to
reliably cover every path. The GitHub Contents API scoped to just this
one directory has no such risk.
"""

import json
import logging
import os
import urllib.request
from urllib.error import HTTPError, URLError

from virtaal.support.dictionary_source import candidate_folders

CONTENTS_URL = 'https://api.github.com/repos/LibreOffice/core/contents/extras/source/autocorr/lang'
RAW_BASE = 'https://raw.githubusercontent.com/LibreOffice/core/master/extras/source/autocorr/lang/'


def list_autocorrect_folders(contents_json):
    """Parse one GitHub contents-API listing of extras/source/autocorr/
    lang into the set of language folder names. Pure function, no I/O.
    Unlike list_dictionary_folders(), a folder's presence here doesn't
    itself confirm it has a DocumentList.xml (this is a plain
    directory listing, not a recursive one) - the download step below
    handles a folder turning out not to have one."""
    return {entry['name'] for entry in contents_json if entry.get('type') == 'dir'}


def find_document_list_folder(locale_code, folders):
    """The most likely folder covering locale_code, or None if
    candidate_folders() has no guess at all. Pure function, no I/O -
    the caller still needs to actually fetch it to find out whether
    that folder really has a DocumentList.xml.

    folders holds the real, hyphenated GitHub directory names
    (e.g. "af-ZA") - candidate_folders() needs them underscore-
    normalised to compare against locale_code, so match on a
    normalised copy and map back to the real name to return."""
    locale_code = locale_code.replace('-', '_')
    normalised_to_real = {folder.replace('-', '_'): folder for folder in folders}
    candidates = candidate_folders(locale_code, normalised_to_real)
    return normalised_to_real[candidates[0]] if candidates else None


# --- Network I/O - thin, replaceable wrappers around the pure logic above ---

def _get(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read()


def fetch_autocorrect_folders():
    """The real, live directory listing - list_autocorrect_folders()'s
    own input."""
    return json.loads(_get(CONTENTS_URL).decode('utf-8'))


def fetch_document_list(folder):
    return _get(RAW_BASE + folder + '/DocumentList.xml')


# --- Where a downloaded DocumentList.xml needs to end up for
#     AutoCorrector to find it ---

def autocorrect_write_dir(locale_code):
    """Where AutoCorrector looks for a downloaded locale's
    DocumentList.xml - one subdirectory per locale, under this app's
    own per-user config directory (unlike enchant, autocorrect has no
    third-party convention of its own to match)."""
    from virtaal.common import pan_app
    return os.path.join(pan_app.get_config_dir(), 'autocorr', locale_code.replace('-', '_'))


def download_document_list(locale_code, target_dir=None):
    """Find and download the DocumentList.xml covering locale_code,
    writing it into target_dir (autocorrect_write_dir(locale_code) by
    default). Returns the local file path written, or None if no
    autocorrect data covers this locale.

    Synchronous, real network I/O - not meant to be called from the
    UI thread as-is; see this module's own docstring."""
    if target_dir is None:
        target_dir = autocorrect_write_dir(locale_code)

    folders = list_autocorrect_folders(fetch_autocorrect_folders())
    folder = find_document_list_folder(locale_code, folders)
    if folder is None:
        logging.debug('No LibreOffice autocorrect folder guess for %s', locale_code)
        return None

    try:
        content = fetch_document_list(folder)
    except (HTTPError, URLError) as e:
        logging.debug('No autocorrect data for %s (folder %s): %s', locale_code, folder, e)
        return None

    os.makedirs(target_dir, exist_ok=True)
    dest = os.path.join(target_dir, 'DocumentList.xml')
    with open(dest, 'wb') as f:
        f.write(content)
    return dest
