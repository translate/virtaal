#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Validate every source Virtaal downloads assets from - LibreOffice's
dictionaries repo (spell-check dictionaries and thesauruses) and its
core repo (autocorrect data) - still resolves to real files, and
optionally emit the combined manifest virtaal.support.asset_manifest
consumes at runtime instead of doing this same discovery live.

Run periodically (see .github/workflows/update-asset-manifest.yml)
so an upstream repo restructuring is caught before a user's download
silently fails. Supersedes the old dictionary-only
devsupport/testing/check_libreoffice_dictionaries.py, widened to cover
every resource type.

Each file's manifest entry gets its git blob sha straight from the
tree/contents listing already being walked to find it - no extra
request per file just to fingerprint it. A locale is only added to the
manifest once every one of its files resolves to a real blob; a
missing file is a validation failure, not a partial manifest entry.
"""

import argparse
import json
import sys
import urllib.request
from urllib.error import HTTPError, URLError

import yaml

from virtaal.support.dictionary_source import (
    fetch_dictionary_tree,
    fetch_xcu,
    list_dictionary_folders,
    parse_dictionaries_xcu,
)

AUTOCORRECT_PARENT_CONTENTS_URL = 'https://api.github.com/repos/LibreOffice/core/contents/extras/source/autocorr'
AUTOCORRECT_TREE_URL = 'https://api.github.com/repos/LibreOffice/core/git/trees/%s?recursive=1'

# Folders with no HunSpellDic_* entry at all, permanently - not an
# upstream restructuring to catch. zu_ZA only ships a hyphenation
# dictionary; hunspell's affix-based approach doesn't suit Zulu well
# enough for a usable spelling dictionary to exist there.
NO_SPELL_DICTIONARY = {'zu_ZA'}


def _get_json(url):
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def blob_shas(tree_json):
    """{repo-relative path: git blob sha} for every blob in one
    recursive git-trees response. Pure function, no I/O."""
    return {e['path']: e.get('sha') for e in tree_json.get('tree', []) if e.get('type') == 'blob'}


def _file_sha(shas, folder, filename):
    # dictionaries.xcu's %origin% is meant to be the folder it lives in
    # itself, and usually is - but a handful of real packages (ca, ckb,
    # fr_FR, sv_SE) nest the actual files one level deeper, in a
    # 'dictionaries/' subfolder alongside other extension bits.
    for candidate in (folder + '/' + filename, folder + '/dictionaries/' + filename):
        if candidate in shas:
            return shas[candidate]
    return None


def check_dictionary_style_folder(folder, shas, dict_format, required):
    """(problems, {locale: {folder, files}}) for one LibreOffice/
    dictionaries folder, of dict_format (DICT_SPELL or DICT_THES).
    `required` controls whether a folder with no entries of this
    format at all is itself a problem (true for the spell-check pass,
    false for thesaurus - most languages simply have none)."""
    try:
        entries = parse_dictionaries_xcu(fetch_xcu(folder), dict_format)
    except Exception as e:
        return (['%s: could not parse dictionaries.xcu (%s)' % (folder, e)], {})
    if not entries:
        if required and folder not in NO_SPELL_DICTIONARY:
            return (['%s: dictionaries.xcu has no %s entries' % (folder, dict_format)], {})
        return ([], {})
    problems = []
    manifest = {}
    for entry in entries:
        files = []
        ok = True
        for filename in entry['files']:
            sha = _file_sha(shas, folder, filename)
            if sha is None:
                problems.append('%s/%s: not found in repo tree' % (folder, filename))
                ok = False
                continue
            files.append({'name': filename, 'sha': sha})
        if not ok:
            continue
        for locale in entry['locales']:
            manifest[locale] = {'folder': folder, 'files': files}
    return (problems, manifest)


def build_dictionary_and_thesaurus_manifests():
    tree = fetch_dictionary_tree()
    folders = list_dictionary_folders(tree)
    shas = blob_shas(tree)
    problems = []
    dictionary = {}
    thesaurus = {}
    for folder in sorted(folders):
        folder_problems, entries = check_dictionary_style_folder(
            folder, shas, 'DICT_SPELL', required=True)
        problems.extend(folder_problems)
        dictionary.update(entries)
        _, thes_entries = check_dictionary_style_folder(
            folder, shas, 'DICT_THES', required=False)
        thesaurus.update(thes_entries)
    return problems, dictionary, thesaurus


def build_autocorrect_manifest():
    """One recursive git-trees call scoped to extras/source/autocorr/
    lang's own subtree (found via one Contents-API call on its parent
    directory) covers every language folder's DocumentList.xml in one
    shot - avoids a separate Contents-API call per language folder
    (~180 of them)."""
    parent = _get_json(AUTOCORRECT_PARENT_CONTENTS_URL)
    lang_dir = next((e for e in parent if e.get('name') == 'lang' and e.get('type') == 'dir'), None)
    if lang_dir is None:
        return (['extras/source/autocorr/lang: not found'], {})
    tree = _get_json(AUTOCORRECT_TREE_URL % lang_dir['sha'])
    autocorrect = {}
    for entry in tree.get('tree', []):
        if entry.get('type') != 'blob' or not entry.get('path', '').endswith('/DocumentList.xml'):
            continue
        folder = entry['path'].rsplit('/', 1)[0]
        locale = folder.replace('-', '_')
        autocorrect[locale] = {
            'folder': folder,
            'files': [{'name': 'DocumentList.xml', 'sha': entry.get('sha')}],
        }
    problems = [] if autocorrect else ['no DocumentList.xml files found under extras/source/autocorr/lang']
    return problems, autocorrect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-out', help='Write the asset manifest YAML here, only if the run is clean')
    args = parser.parse_args()

    dict_problems, dictionary, thesaurus = build_dictionary_and_thesaurus_manifests()
    try:
        autocorrect_problems, autocorrect = build_autocorrect_manifest()
    except (HTTPError, URLError, ValueError) as e:
        autocorrect_problems, autocorrect = (['autocorrect: %s' % e], {})
    problems = dict_problems + autocorrect_problems

    if problems:
        print('%d problem(s) found:' % len(problems))
        for p in problems:
            print(' -', p)
        return 1

    print('%d dictionary, %d thesaurus, %d autocorrect locale(s) resolve cleanly.'
          % (len(dictionary), len(thesaurus), len(autocorrect)))

    if args.manifest_out:
        manifest = {'dictionary': dictionary, 'thesaurus': thesaurus, 'autocorrect': autocorrect}
        with open(args.manifest_out, 'w', encoding='utf-8') as f:
            yaml.safe_dump(manifest, f)
        print('Wrote manifest to %s' % args.manifest_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
