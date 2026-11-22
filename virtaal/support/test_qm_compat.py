#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.storage import factory, qm

from virtaal.support import qm_compat  # noqa: F401 - applies its patch on import


def test_qm_unit_hasplural_true_for_a_real_plural():
    store = factory.getobject('devsupport/testfiles/workflow.qm')
    plural_unit = next(u for u in store.units if u.source.startswith('%n'))
    assert plural_unit.hasplural() is True


def test_qm_unit_hasplural_false_for_a_plain_string():
    store = factory.getobject('devsupport/testfiles/workflow.qm')
    plain_unit = next(u for u in store.units if u.source == 'Open')
    assert plain_unit.hasplural() is False


# Built by Qt 6 lrelease from qm-utf8-sources.ts.
def _sources(name):
    store = factory.getobject('devsupport/testfiles/' + name)
    return [u.source for u in store.units]


def test_qm_utf8_sources_decode_as_utf8():
    sources = _sources('qm-utf8-sources.qm')
    assert 'Café menu — “Open”' in sources


def test_qm_length_variant_separator_decodes_as_utf8():
    sources = _sources('qm-utf8-sources.qm')
    assert 'Save the current document\u009cSave document\u009cSave' in sources


def test_qm_ascii_source_unchanged():
    assert 'Open' in _sources('qm-utf8-sources.qm')


def test_qm_utf8_targets_unchanged():
    store = factory.getobject('devsupport/testfiles/qm-utf8-sources.qm')
    unit = next(u for u in store.units if u.source.endswith('\u201cOpen\u201d'))
    assert unit.target == 'Kafee-kieslys — “Maak oop”'


# An old Latin-1 .qm: the e-acute byte E9 isn't valid UTF-8, so the whole
# file stays Latin-1, including the bytes C3 A9, which would decode as UTF-8.
def test_qm_latin1_sources_stay_latin1():
    assert _sources('qm-latin1-sources.qm') == [
        'Café menu', 'Lat\u00c3\u00a9 sign']


def test_qm_patch_wraps_the_original_parse_once():
    assert qm_compat._qm_parse is qm.qmfile.parse.__wrapped__
    assert not hasattr(qm_compat._qm_parse, '__wrapped__')
