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

"""Tests for AutoCorrector's load_dictionary()/_read_document_list()
and autocorrect() - the plain data logic, no real GTK widgets
involved. Fixture content is the same real, live-fetched af-ZA
DocumentList.xml excerpt test_autocorrect_source.py already uses."""

from virtaal.plugins.autocorrector import AutoCorrector
from virtaal.support.test_autocorrect_source import AF_ZA_DOCUMENT_LIST


def _write_document_list(acorpath, lang, content=AF_ZA_DOCUMENT_LIST):
    lang_dir = acorpath / lang
    lang_dir.mkdir(parents=True, exist_ok=True)
    (lang_dir / 'DocumentList.xml').write_bytes(content)


def test_load_dictionary_with_nothing_local_is_empty(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    assert corrector.correctiondict == {}
    assert corrector.lang == ''


def test_load_dictionary_reads_the_exact_locale_directory(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.load_dictionary('af_ZA')

    assert corrector.lang == 'af_ZA'
    assert 'adt' in corrector.correctiondict
    assert corrector.correctiondict['adt'][0] == 'dat'


def test_load_dictionary_accepts_hyphenated_input(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.load_dictionary('af-ZA')

    assert corrector.lang == 'af_ZA'
    assert 'basseer' in corrector.correctiondict


def test_load_dictionary_falls_back_to_bare_language_directory(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.load_dictionary('af')

    assert corrector.lang == 'af'
    assert 'adt' in corrector.correctiondict


def test_load_dictionary_short_circuits_on_the_same_language(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    corrector.correctiondict['sentinel'] = 'still here'

    corrector.load_dictionary('af_ZA')  # same lang, no force -> no-op

    assert 'sentinel' in corrector.correctiondict


def test_load_dictionary_force_reloads_the_same_language(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    assert corrector.correctiondict == {}

    # Simulate a download landing after the first (empty) attempt.
    _write_document_list(tmp_path, 'af_ZA')
    corrector.load_dictionary('af_ZA', force=True)

    assert 'adt' in corrector.correctiondict


def test_autocorrect_replaces_a_known_abbreviation(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')

    reprange, replacement = corrector.autocorrect('Ek adt', 6)

    assert replacement == 'dat'
    assert reprange == (3, 6)


def test_autocorrect_with_no_dictionary_does_nothing(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    reprange, replacement = corrector.autocorrect('Ek adt', 6)

    assert reprange is None
    assert replacement == ''
