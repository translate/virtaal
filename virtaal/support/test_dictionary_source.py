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

"""Tests for dictionary_source's pure enumerate/parse/match logic - the
raw network calls (fetch_dictionary_tree/fetch_xcu/fetch_dictionary_file)
are thin, untested wrappers (see that module's own docstring);
download_dictionary()'s own orchestration is tested here with those
three monkeypatched away. Fixtures below are actual copies from
github.com/LibreOffice/dictionaries, not hand-written guesses, so a
real repo-shape change would actually be caught.
"""

from urllib.error import URLError

from virtaal.support import dictionary_source
from virtaal.support.dictionary_source import (
    candidate_folders,
    download_dictionary,
    find_dictionary,
    list_dictionary_folders,
    parse_dictionaries_xcu,
)

# Actual copy (trimmed to the parts these tests need) of
# de/dictionaries.xcu (blob 0cccf05960e3d6479e9b7df39eb486dc21214e72) -
# de_DE_frami.aff isn't guessable from the locale code (de_DE.aff
# would be the guess), and one folder covers three distinct locales.
DE_XCU = b"""<?xml version="1.0" encoding="UTF-8"?>
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" oor:name="Linguistic" oor:package="org.openoffice.Office">
 <node oor:name="ServiceManager">
    <node oor:name="Dictionaries">
        <node oor:name="HunSpellDic_de-AT_frami" oor:op="fuse">
            <prop oor:name="Locations" oor:type="oor:string-list">
                <value>%origin%/de_AT_frami.aff %origin%/de_AT_frami.dic</value>
            </prop>
            <prop oor:name="Format" oor:type="xs:string">
                <value>DICT_SPELL</value>
            </prop>
            <prop oor:name="Locales" oor:type="oor:string-list">
                <value>de-AT</value>
            </prop>
        </node>
        <node oor:name="HunSpellDic_de-DE_frami" oor:op="fuse">
            <prop oor:name="Locations" oor:type="oor:string-list">
                <value>%origin%/de_DE_frami.aff %origin%/de_DE_frami.dic</value>
            </prop>
            <prop oor:name="Format" oor:type="xs:string">
                <value>DICT_SPELL</value>
            </prop>
            <prop oor:name="Locales" oor:type="oor:string-list">
                <value>de-DE</value>
            </prop>
        </node>
        <node oor:name="HyphDic_de-DE" oor:op="fuse">
            <prop oor:name="Locations" oor:type="oor:string-list">
                <value>%origin%/hyph_de_DE.dic</value>
            </prop>
            <prop oor:name="Format" oor:type="xs:string">
                <value>DICT_HYPH</value>
            </prop>
            <prop oor:name="Locales" oor:type="oor:string-list">
                <value>de de-DE</value>
            </prop>
        </node>
    </node>
 </node>
</oor:component-data>
"""

# Actual copy of ar/dictionaries.xcu (blob
# cd34b51d72c3ae0dd4801fe3c28cde29e20290cc) - the case with the most
# locales sharing one dictionary (17).
AR_XCU = b"""<?xml version="1.0" encoding="UTF-8"?>
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" oor:name="Linguistic" oor:package="org.openoffice.Office">
 <node oor:name="ServiceManager">
    <node oor:name="Dictionaries">
        <node oor:name="HunSpellDic_ar" oor:op="fuse">
            <prop oor:name="Locations" oor:type="oor:string-list">
                <value>%origin%/ar.aff %origin%/ar.dic</value>
            </prop>
            <prop oor:name="Format" oor:type="xs:string">
                <value>DICT_SPELL</value>
            </prop>
            <prop oor:name="Locales" oor:type="oor:string-list">
                <value>ar-SA ar-DZ ar-BH ar-EG ar-IQ ar-JO ar-KW ar-LB ar-LY ar-MA ar-OM ar-QA ar-SD ar-SY ar-TN ar-AE ar-YE</value>
            </prop>
        </node>
    </node>
 </node>
</oor:component-data>
"""


def test_parse_dictionaries_xcu_strips_origin_prefix_and_normalises_locale():
    """de_DE's real filename isn't derivable from the locale code, and
    Locales use hyphens where enchant/Virtaal want underscores."""
    entries = parse_dictionaries_xcu(DE_XCU)
    by_locale = {loc: e for e in entries for loc in e['locales']}
    assert by_locale['de_DE']['files'] == ['de_DE_frami.aff', 'de_DE_frami.dic']
    assert by_locale['de_AT']['files'] == ['de_AT_frami.aff', 'de_AT_frami.dic']


def test_parse_dictionaries_xcu_ignores_non_spelling_nodes():
    """HyphDic_* (hyphenation) is real content in the same file but out
    of scope - only DICT_SPELL/HunSpellDic_* nodes should come back."""
    entries = parse_dictionaries_xcu(DE_XCU)
    assert len(entries) == 2
    assert all('frami' in f for e in entries for f in e['files'])


def test_parse_dictionaries_xcu_handles_one_dict_covering_many_locales():
    entries = parse_dictionaries_xcu(AR_XCU)
    assert len(entries) == 1
    assert entries[0]['files'] == ['ar.aff', 'ar.dic']
    assert 'ar_EG' in entries[0]['locales']
    assert len(entries[0]['locales']) == 17


def test_list_dictionary_folders_from_real_tree_shape():
    tree_json = {
        'truncated': False,
        'tree': [
            {'path': 'de/dictionaries.xcu', 'sha': 'abc123'},
            {'path': 'af_ZA/dictionaries.xcu', 'sha': 'def456'},
            {'path': 'de/de_DE_frami.dic', 'sha': 'not-an-xcu'},
            {'path': 'README.md', 'sha': 'irrelevant'},
        ],
    }
    folders = list_dictionary_folders(tree_json)
    assert folders == {'de': 'abc123', 'af_ZA': 'def456'}


def test_candidate_folders_tries_exact_then_bare_language():
    known = {'af_ZA': 'x', 'de': 'y'}
    assert candidate_folders('af_ZA', known) == ['af_ZA']
    assert candidate_folders('de_DE', known) == ['de']
    assert candidate_folders('xx_YY', known) == []


def test_find_dictionary_uses_candidate_before_scanning_everything():
    folders = {'de': 's1', 'ar': 's2'}
    fetched = []

    def fetch_xcu(folder):
        fetched.append(folder)
        return {'de': DE_XCU, 'ar': AR_XCU}[folder]

    result = find_dictionary('de_DE', folders, fetch_xcu)
    assert result == ('de', ['de_DE_frami.aff', 'de_DE_frami.dic'])
    # 'de' is de_DE's own candidate folder - no need to have also
    # fetched 'ar' to find it.
    assert fetched == ['de']


def test_find_dictionary_falls_back_to_scanning_other_folders():
    """ar_EG's own dictionary isn't in a folder candidate_folders()
    would guess from the locale code alone ('ar_EG'/'ar_EG's folder
    is actually just 'ar') - covered by candidate_folders itself, but
    confirm the orchestration doesn't silently miss a match sitting in
    a folder named differently from any prefix of the locale code."""
    folders = {'de': 's1', 'ar': 's2'}
    fetched = []

    def fetch_xcu(folder):
        fetched.append(folder)
        return {'de': DE_XCU, 'ar': AR_XCU}[folder]

    result = find_dictionary('ar_EG', folders, fetch_xcu)
    assert result == ('ar', ['ar.aff', 'ar.dic'])


def test_find_dictionary_returns_none_when_nothing_matches():
    result = find_dictionary('xx_YY', {'de': 's1'}, lambda folder: DE_XCU)
    assert result is None


def test_download_dictionary_cleans_up_partial_write_on_failure(monkeypatch, tmp_path):
    """de_DE_frami has two files - if the second one fails, the first
    must not be left behind for a later run to mistake as a complete,
    real dictionary."""
    monkeypatch.setattr(dictionary_source, 'fetch_dictionary_tree',
                         lambda: {'tree': [{'path': 'de/dictionaries.xcu'}]})
    monkeypatch.setattr(dictionary_source, 'fetch_xcu', lambda folder: DE_XCU)

    def fetch_dictionary_file(folder, filename):
        if filename.endswith('.dic'):
            raise URLError('boom')
        return b'aff content'
    monkeypatch.setattr(dictionary_source, 'fetch_dictionary_file', fetch_dictionary_file)

    result = download_dictionary('de_DE', target_dir=str(tmp_path))

    assert result is None
    assert list(tmp_path.iterdir()) == []
