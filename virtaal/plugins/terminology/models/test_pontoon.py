#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import configparser
import io
import os
import time
from types import SimpleNamespace

import pytest
from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.plugins.terminology.models.pontoon import (
    TerminologyModel,
    _is_english,
    _parse_tbx_basic,
    _pontoon_locale_code,
)


class _FakeRequest:
    status = 200

    def __init__(self, headers=b'ETag: "abc123"\r\n', effective_url='https://example.com/terms.tbx'):
        self.result_headers = io.BytesIO(headers)
        self._effective_url = effective_url

    def get_effective_url(self):
        return self._effective_url


@pytest.fixture(autouse=True)
def _isolate_terminology_matchers():
    # A module-level list shared across the whole process - restore it
    # so tests here don't leak matchers into unrelated test files.
    original = list(TerminologyPlaceable.matchers)
    yield
    TerminologyPlaceable.matchers[:] = original


def _model(tmp_path, **attrs):
    model = TerminologyModel.__new__(TerminologyModel)
    model.TERMDIR = str(tmp_path)
    model.config = {}
    model.matcher = None
    for name, value in attrs.items():
        setattr(model, name, value)
    return model


def test_process_header_config_key_is_a_bare_filename(tmp_path):
    """self.config used to be keyed by an absolute path, which on Windows
    always contains ":" - a char configparser rejects in a key."""
    fake_self = TerminologyModel.__new__(TerminologyModel)
    fake_self.config = {}
    fake_self.matcher = None

    localfile = os.path.join(str(tmp_path), 'en__am.tbx')
    TerminologyModel._process_header(fake_self, _FakeRequest(), b'<tbx/>', localfile=localfile)

    assert list(fake_self.config.keys()) == ['en__am.tbx']
    assert os.path.isfile(localfile)

    # Confirm the key actually survives a real configparser round-trip.
    parser = configparser.ConfigParser()
    parser.add_section('pontoon')
    for key, value in fake_self.config.items():
        parser.set('pontoon', key, value)
    parser.write(io.StringIO())  # raises configparser.InvalidWriteError if broken


# _is_english() / _pontoon_locale_code(): Pontoon is English-source
# only, and its static files are named with case/separator rules that
# don't match Virtaal's own language-code normalization.

@pytest.mark.parametrize('code', ['en', 'en_US', 'en-GB', 'EN', 'en_ZA'])
def test_is_english_accepts_any_english_variant(code):
    assert _is_english(code) is True


@pytest.mark.parametrize('code', ['af', 'pt_BR', 'fr', ''])
def test_is_english_rejects_non_english(code):
    assert _is_english(code) is False


def test_is_english_rejects_none():
    assert _is_english(None) is False


def test_pontoon_locale_code_uppercases_the_region_and_uses_a_hyphen():
    assert _pontoon_locale_code('en_gb') == 'en-GB'


def test_pontoon_locale_code_leaves_a_bare_language_code_unchanged():
    assert _pontoon_locale_code('af') == 'af'


def test_pontoon_locale_code_does_not_lowercase_the_whole_code():
    # normalize_code() alone lowercases everything, which 404s against
    # Pontoon's case-sensitive server - the region must stay uppercase.
    assert _pontoon_locale_code('pt_br') == 'pt-BR'


# _parse_tbx_basic(): Pontoon's TBX-Basic export, parsed directly since
# translate-toolkit's own tbx.py targets the older MARTIF-rooted TBX.

_TBX_NS = 'urn:iso:std:iso:30042:ed-2'
_XML_NS = 'http://www.w3.org/XML/1998/namespace'


def _tbx(*entries):
    body = '\n'.join(entries)
    return ('<tbx xmlns="%s" style="dca" type="TBX-Basic">'
            '<text><body>%s</body></text></tbx>' % (_TBX_NS, body)).encode('utf-8')


def _concept_entry(pairs):
    langsecs = ''.join(
        '<langSec xml:lang="%s"><termSec><term>%s</term></termSec></langSec>' % (lang, term)
        for lang, term in pairs)
    return '<conceptEntry>%s</conceptEntry>' % langsecs


def test_parse_tbx_basic_extracts_the_source_and_target_terms():
    content = _tbx(_concept_entry([('en', 'Hello'), ('af', 'Hallo')]))

    store = _parse_tbx_basic(content)

    assert len(store.units) == 1
    assert store.units[0].source == 'Hello'
    assert store.units[0].target == 'Hallo'


def test_parse_tbx_basic_skips_an_entry_missing_a_target_term():
    content = _tbx(_concept_entry([('en', 'Hello')]))

    store = _parse_tbx_basic(content)

    assert len(store.units) == 0


def test_parse_tbx_basic_skips_an_entry_missing_the_english_source():
    content = _tbx(_concept_entry([('af', 'Hallo')]))

    store = _parse_tbx_basic(content)

    assert len(store.units) == 0


def test_parse_tbx_basic_skips_a_langsec_with_no_term_text():
    content = _tbx('<conceptEntry><langSec xml:lang="en"><termSec></termSec></langSec>'
                    '<langSec xml:lang="af"><termSec><term>Hallo</term></termSec></langSec></conceptEntry>')

    store = _parse_tbx_basic(content)

    assert len(store.units) == 0


def test_parse_tbx_basic_returns_an_empty_store_for_an_empty_body():
    content = _tbx()

    store = _parse_tbx_basic(content)

    assert len(store.units) == 0


def test_parse_tbx_basic_returns_an_empty_store_for_malformed_xml():
    store = _parse_tbx_basic(b'not xml at all <<<')

    assert len(store.units) == 0


def test_parse_tbx_basic_handles_multiple_concept_entries():
    content = _tbx(
        _concept_entry([('en', 'Hello'), ('af', 'Hallo')]),
        _concept_entry([('en', 'Goodbye'), ('af', 'Totsiens')]),
    )

    store = _parse_tbx_basic(content)

    assert [(u.source, u.target) for u in store.units] == [('Hello', 'Hallo'), ('Goodbye', 'Totsiens')]


# _get_curr_term_filename(): find an already-downloaded file for a
# language pair regardless of its extension, or name a new one.

def test_curr_term_filename_finds_an_existing_file_regardless_of_extension(tmp_path):
    (tmp_path / 'en__af.po').write_text('')
    model = _model(tmp_path, source_lang='en', target_lang='af')

    assert model.curr_term_filename == 'en__af.po'


def test_curr_term_filename_defaults_to_tbx_for_a_new_pair(tmp_path):
    model = _model(tmp_path, source_lang='en', target_lang='af')

    assert model.curr_term_filename == 'en__af.tbx'


# is_update_needed(): a missing file always needs fetching; an
# existing one only after it's more than three days old.

def test_is_update_needed_true_when_no_local_file_exists(tmp_path):
    model = _model(tmp_path, source_lang='en', target_lang='af')

    assert model.is_update_needed('en', 'af') is True


def test_is_update_needed_false_for_a_fresh_file(tmp_path):
    (tmp_path / 'en__af.tbx').write_text('')
    model = _model(tmp_path, source_lang='en', target_lang='af')

    assert model.is_update_needed('en', 'af') is False


def test_is_update_needed_true_for_a_stale_file(tmp_path):
    localfile = tmp_path / 'en__af.tbx'
    localfile.write_text('')
    stale = time.time() - (60 * 60 * 24 * 4)  # 4 days old
    os.utime(str(localfile), (stale, stale))
    model = _model(tmp_path, source_lang='en', target_lang='af')

    assert model.is_update_needed('en', 'af') is True


# update_terms(): the top-level dispatch - English-source gate,
# staleness check, and delegating an actual fetch.

def test_update_terms_does_nothing_when_both_languages_are_unset(tmp_path):
    model = _model(tmp_path, source_lang=None, target_lang=None)
    model.init_matcher = lambda filename='': pytest.fail('should not touch the matcher')
    model._update_term_file = lambda *a: pytest.fail('should not fetch')

    model.update_terms()


def test_update_terms_requires_both_languages_or_neither(tmp_path):
    model = _model(tmp_path, source_lang='en', target_lang=None)

    with pytest.raises(ValueError):
        model.update_terms(srclang='fr')


def test_update_terms_uses_an_empty_store_for_a_non_english_source(tmp_path):
    model = _model(tmp_path, source_lang='af', target_lang='en')
    matched = []
    model.init_matcher = lambda filename='': matched.append(filename)

    model.update_terms('af', 'en')

    assert matched == ['']


def test_update_terms_reuses_a_fresh_local_file_without_fetching(tmp_path):
    (tmp_path / 'en__af.tbx').write_text('')
    model = _model(tmp_path, source_lang='en', target_lang='af')
    matched = []
    model.init_matcher = lambda filename='': matched.append(filename)
    model._update_term_file = lambda *a: pytest.fail('should not fetch a fresh file')

    model.update_terms('en', 'af')

    assert matched == [str(tmp_path / 'en__af.tbx')]


def test_update_terms_fetches_when_the_local_file_is_stale_or_missing(tmp_path):
    model = _model(tmp_path, source_lang='en', target_lang='af')
    fetched = []
    model._update_term_file = lambda srclang, tgtlang: fetched.append((srclang, tgtlang))

    model.update_terms('en', 'af')

    assert fetched == [('en', 'af')]


# _get_ext_from_url()

def test_get_ext_from_url_reads_the_path_extension(tmp_path):
    model = _model(tmp_path)
    assert model._get_ext_from_url('https://pontoon.mozilla.org/terminology/af.tbx') == 'tbx'


def test_get_ext_from_url_returns_none_without_an_extension(tmp_path):
    model = _model(tmp_path)
    assert model._get_ext_from_url('https://pontoon.mozilla.org/terminology/af') is None


def test_get_ext_from_url_returns_none_for_an_empty_path(tmp_path):
    model = _model(tmp_path)
    assert model._get_ext_from_url('https://pontoon.mozilla.org') is None


# _process_header(): saving a fetched file, deriving its extension
# when the caller doesn't already know it, and the ETag bookkeeping
# that drives future conditional requests.

def test_process_header_skips_saving_on_a_304_not_modified(tmp_path):
    model = _model(tmp_path)
    matched = []
    model.init_matcher = lambda filename='': matched.append(filename)
    request = SimpleNamespace(status=304)

    model._process_header(request, b'', localfile='/tmp/unused.tbx')

    assert matched == ['/tmp/unused.tbx']
    assert model.config == {}


def test_process_header_saves_the_file_and_records_its_etag(tmp_path):
    model = _model(tmp_path)
    model.init_matcher = lambda filename='': None
    localfile = str(tmp_path / 'en__af.tbx')

    model._process_header(_FakeRequest(), b'<tbx/>', localfile=localfile)

    assert (tmp_path / 'en__af.tbx').read_bytes() == b'<tbx/>'
    assert model.config == {'en__af.tbx': 'abc123'}


def test_process_header_derives_the_filename_and_extension_when_not_given(tmp_path):
    model = _model(tmp_path, source_lang='en', target_lang='af')
    model.init_matcher = lambda filename='': None
    request = _FakeRequest(effective_url='https://pontoon.mozilla.org/terminology/af.tbx')

    model._process_header(request, b'<tbx/>', localfile=None)

    assert (tmp_path / 'en__af.tbx').is_file()
    assert model.config == {'en__af.tbx': 'abc123'}


def test_process_header_falls_back_to_po_when_no_extension_can_be_determined(tmp_path):
    model = _model(tmp_path, source_lang='en', target_lang='af')
    model.init_matcher = lambda filename='': None
    request = _FakeRequest(effective_url='https://pontoon.mozilla.org/terminology/af', headers=b'')

    model._process_header(request, b'not a recognizable store format', localfile=None)

    assert (tmp_path / 'en__af.po').is_file()


def test_process_header_records_no_etag_when_the_response_has_none(tmp_path):
    model = _model(tmp_path)
    model.init_matcher = lambda filename='': None
    localfile = str(tmp_path / 'en__af.tbx')

    model._process_header(_FakeRequest(headers=b''), b'<tbx/>', localfile=localfile)

    assert model.config == {'en__af.tbx': ''}


def test_process_header_clears_the_matcher_on_an_unhandled_status(tmp_path):
    model = _model(tmp_path)
    matched = []
    model.init_matcher = lambda filename='': matched.append(filename)
    request = SimpleNamespace(status=500)

    model._process_header(request, b'', localfile='/tmp/unused.tbx')

    assert matched == ['']
    assert model.config == {}


# _on_lang_changed(): re-fetches terminology for whichever side of the
# language pair just changed.

def test_on_lang_changed_updates_the_relevant_language_and_refetches(tmp_path):
    model = _model(tmp_path, source_lang='en', target_lang='af')
    calls = []
    model.update_terms = lambda srclang, tgtlang: calls.append((srclang, tgtlang))

    model._on_lang_changed(None, 'fr', 'target')

    assert model.target_lang == 'fr'
    assert calls == [('en', 'fr')]
