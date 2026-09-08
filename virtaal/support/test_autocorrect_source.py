#!/usr/bin/env python
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

"""Tests for autocorrect_source's pure enumerate/match logic - the raw
network calls (fetch_autocorrect_folders/fetch_document_list) are
thin, untested wrappers; download_document_list()'s own orchestration
is tested here with those two monkeypatched away.
"""

from urllib.error import HTTPError

from virtaal.support import autocorrect_source
from virtaal.support.autocorrect_source import (
    download_document_list,
    find_document_list_folder,
    list_autocorrect_folders,
)

# Actual copy (trimmed to the entries these tests need) of
# af-ZA/DocumentList.xml from github.com/LibreOffice/core.
AF_ZA_DOCUMENT_LIST = b"""<?xml version="1.0" encoding="utf-8"?>
<block-list:block-list xmlns:block-list="http://openoffice.org/2001/block-list">
  <block-list:block block-list:abbreviated-name="adt" block-list:name="dat"/>
  <block-list:block block-list:abbreviated-name="basseer" block-list:name="baseer"/>
</block-list:block-list>
"""

# Real listing shape from a live GitHub Contents API request against
# extras/source/autocorr/lang (trimmed to a handful of entries) -
# LibreOffice/core is too large for a recursive git-trees call to
# reliably cover this directory; this scoped listing doesn't have
# that problem.
CONTENTS_LISTING = [
    {'name': 'af-ZA', 'type': 'dir'},
    {'name': 'de', 'type': 'dir'},
    {'name': 'en-GB', 'type': 'dir'},
    {'name': 'README.txt', 'type': 'file'},
]


def test_list_autocorrect_folders_ignores_non_directory_entries():
    folders = list_autocorrect_folders(CONTENTS_LISTING)
    assert folders == {'af-ZA', 'de', 'en-GB'}


def test_find_document_list_folder_prefers_exact_match():
    """Real folders are hyphenated ('af-ZA', GitHub's own naming) -
    locale_code ('af_ZA') needs matching against a normalised copy,
    then mapping back to the real, hyphenated name to fetch."""
    folders = {'af-ZA', 'de'}
    assert find_document_list_folder('af_ZA', folders) == 'af-ZA'


def test_find_document_list_folder_falls_back_to_bare_language():
    folders = {'de'}
    assert find_document_list_folder('de_DE', folders) == 'de'


def test_find_document_list_folder_returns_none_when_nothing_matches():
    folders = {'de'}
    assert find_document_list_folder('xx_YY', folders) is None


def test_download_document_list_writes_the_real_file(monkeypatch, tmp_path):
    monkeypatch.setattr(autocorrect_source, 'fetch_autocorrect_folders',
                         lambda: CONTENTS_LISTING)
    monkeypatch.setattr(autocorrect_source, 'fetch_document_list',
                         lambda folder: {'af-ZA': AF_ZA_DOCUMENT_LIST}[folder])

    dest = download_document_list('af_ZA', target_dir=str(tmp_path))

    assert dest == str(tmp_path / 'DocumentList.xml')
    assert (tmp_path / 'DocumentList.xml').read_bytes() == AF_ZA_DOCUMENT_LIST


def test_download_document_list_returns_none_when_no_folder_guess(monkeypatch, tmp_path):
    monkeypatch.setattr(autocorrect_source, 'fetch_autocorrect_folders',
                         lambda: CONTENTS_LISTING)
    result = download_document_list('xx_YY', target_dir=str(tmp_path))
    assert result is None


def test_download_document_list_returns_none_on_a_real_404(monkeypatch, tmp_path):
    """A folder can exist (it's a real GitHub directory) without a
    DocumentList.xml inside it - the Contents-API listing only proves
    the directory exists, not its contents."""
    def fetch_document_list_404(folder):
        raise HTTPError(autocorrect_source.RAW_BASE + folder, 404, 'Not Found', None, None)

    monkeypatch.setattr(autocorrect_source, 'fetch_autocorrect_folders',
                         lambda: CONTENTS_LISTING)
    monkeypatch.setattr(autocorrect_source, 'fetch_document_list', fetch_document_list_404)

    result = download_document_list('af_ZA', target_dir=str(tmp_path))
    assert result is None
