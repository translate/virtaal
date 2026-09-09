#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Source hunspell spell-check dictionaries directly from LibreOffice's
own dictionaries repo (github.com/LibreOffice/dictionaries) - LibreOffice
is hunspell's own reference consumer, and the de facto community source.

Two-step lookup, matching the repo's real shape:

1. Enumerate every language folder via one recursive git-trees call
   (list_dictionary_folders()).
2. Per folder, read its own dictionaries.xcu (parse_dictionaries_xcu())
   - the authoritative source for both the real .aff/.dic filenames
   (not derivable from the locale code: German's is de_DE_frami.aff,
   not de_DE.aff) and the full list of locale codes that dictionary
   covers (Arabic's one dictionary covers 17 country variants).

Deliberately synchronous (plain urllib), not wired into the app's own
async HTTPClient/idle-download machinery yet - that integration is a
separate, later step. Every network call is a thin wrapper so the
parsing/matching logic above is independently testable without a
network connection.
"""

import json
import logging
import os
import urllib.request
from urllib.error import HTTPError, URLError

from lxml import etree

TREE_URL = 'https://api.github.com/repos/LibreOffice/dictionaries/git/trees/master?recursive=1'
RAW_BASE = 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/'

_OOR = '{http://openoffice.org/2001/registry}'
_XCU_SUFFIX = '/dictionaries.xcu'


def list_dictionary_folders(tree_json):
    """Parse one recursive git-trees API response (already-decoded
    JSON) into {folder_path: xcu_blob_sha}, one entry per language
    folder that has its own dictionaries.xcu. Pure function, no I/O."""
    if tree_json.get('truncated'):
        logging.warning(
            'LibreOffice dictionaries tree response was truncated - '
            'some languages may be missing')
    return {
        entry['path'][:-len(_XCU_SUFFIX)]: entry.get('sha')
        for entry in tree_json.get('tree', [])
        if entry.get('path', '').endswith(_XCU_SUFFIX)
    }


def _prop_value(node, prop_name):
    for prop in node.iterfind('prop'):
        if prop.get(_OOR + 'name') == prop_name:
            value = prop.find('value')
            return value.text if value is not None else None
    return None


def parse_dictionaries_xcu(xml_bytes):
    """Parse one folder's dictionaries.xcu into a list of
    {'files': [...], 'locales': [...]} dicts, one per HunSpellDic_*
    node (Format == DICT_SPELL specifically - hyphenation/thesaurus
    nodes in the same file are real but out of scope here). 'files'
    are bare filenames (the "%origin%/" prefix stripped); 'locales'
    are underscore-normalised (enchant's own convention), not the
    repo's hyphenated BCP47 form. Pure function, no I/O."""
    root = etree.fromstring(xml_bytes)
    result = []
    for node in root.iter('node'):
        name = node.get(_OOR + 'name', '')
        if not name.startswith('HunSpellDic_'):
            continue
        if _prop_value(node, 'Format') != 'DICT_SPELL':
            continue
        locations = (_prop_value(node, 'Locations') or '').split()
        files = [
            f[len('%origin%/'):] if f.startswith('%origin%/') else f
            for f in locations
        ]
        locales = [
            loc.replace('-', '_')
            for loc in (_prop_value(node, 'Locales') or '').split()
        ]
        if files and locales:
            result.append({'files': files, 'locales': locales})
    return result


def candidate_folders(locale_code, known_folders):
    """Folder names worth trying first for locale_code (e.g. 'de_DE'),
    cheapest/most-specific first, given the set of real folder names
    already known from list_dictionary_folders(). Real folder naming
    isn't one consistent pattern - some are bare language codes
    covering many regions in one dictionaries.xcu ('ar', 'de'), others
    are the full underscored locale ('af_ZA') - so try the exact
    match, then the bare language part, before falling back to a full
    scan elsewhere. Doesn't guarantee a hit; the caller still needs to
    check the actual xcu content.

    A bare language code with no region of its own (just 'af', not
    'af_ZA') also gets the single folder starting with 'af_', if
    there's exactly one - some languages (af, ga, lb...) only exist
    as one region-qualified folder, with no bare fallback. Left alone
    when there's more than one such folder (en, pt, sr, zh...): no
    good way to guess the right region from a bare code alone."""
    locale_code = locale_code.replace('-', '_')
    lang = locale_code.split('_')[0]
    candidates = [c for c in (locale_code, lang) if c in known_folders]
    if not candidates:
        prefix_matches = [f for f in known_folders if f.startswith(lang + '_')]
        if len(prefix_matches) == 1:
            candidates = prefix_matches
    # Stable order, no duplicates, without needing a set (small lists).
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen


def find_dictionary(locale_code, folders, fetch_xcu):
    """Find the HunSpellDic_* entry covering locale_code.

    folders: {folder_path: sha}, from list_dictionary_folders().
    fetch_xcu: callable(folder_path) -> xcu bytes - injected so this
    is testable without real network access.

    Tries the likely candidate folders first (candidate_folders());
    falls back to every remaining folder if none of those actually
    cover this locale, since folder naming isn't fully predictable.
    Returns (folder_path, files) for the first match, or None.
    """
    locale_code = locale_code.replace('-', '_')
    ordered = candidate_folders(locale_code, folders)
    ordered += [f for f in folders if f not in ordered]
    for folder in ordered:
        for entry in parse_dictionaries_xcu(fetch_xcu(folder)):
            if locale_code in entry['locales']:
                return folder, entry['files']
    return None


# --- Network I/O - thin, replaceable wrappers around the pure logic above ---

def _get(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read()


def fetch_dictionary_tree():
    """The real, live git-trees listing - list_dictionary_folders()'s
    own input."""
    return json.loads(_get(TREE_URL).decode('utf-8'))


def fetch_xcu(folder):
    return _get(RAW_BASE + folder + _XCU_SUFFIX)


def fetch_dictionary_file(folder, filename):
    return _get(RAW_BASE + folder + '/' + filename)


# --- Where downloaded dictionaries need to end up for enchant to find them ---

def dictionary_write_dir():
    """Where enchant's hunspell backend looks for user-installed
    dictionaries.

    Confirmed against libenchant's own current source (rrthomas/enchant,
    lib/provider.vala): a provider's user dict dir is
    get_user_config_dir()/<provider's own identify string>, and the
    hunspell provider's identify() returns literally "hunspell" -
    matching enchant.get_user_config_dir() (Python) plus that name.
    """
    import enchant
    return os.path.join(enchant.get_user_config_dir(), 'hunspell')


def download_dictionary(locale_code, target_dir=None):
    """Find and download the hunspell dictionary covering locale_code,
    writing its files into target_dir (dictionary_write_dir() by
    default). Returns the list of local file paths written, or None if
    no dictionary covers this locale.

    Synchronous, real network I/O - not meant to be called from the
    UI thread as-is; see this module's own docstring."""
    if target_dir is None:
        target_dir = dictionary_write_dir()

    tree = fetch_dictionary_tree()
    folders = list_dictionary_folders(tree)
    match = find_dictionary(locale_code, folders, fetch_xcu)
    if match is None:
        logging.debug('No LibreOffice dictionary found for %s', locale_code)
        return None
    folder, files = match

    os.makedirs(target_dir, exist_ok=True)
    written = []
    for filename in files:
        try:
            content = fetch_dictionary_file(folder, filename)
        except (HTTPError, URLError) as e:
            logging.warning('Could not download %s/%s: %s', folder, filename, e)
            # A dictionary needs every one of its files (e.g. .aff
            # without .dic is useless to enchant) - don't leave a
            # partial one behind for a later run to mistake as real.
            for path in written:
                os.remove(path)
            return None
        dest = os.path.join(target_dir, filename)
        with open(dest, 'wb') as f:
            f.write(content)
        written.append(dest)
    return written
