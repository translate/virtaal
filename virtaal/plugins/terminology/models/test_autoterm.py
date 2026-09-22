#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import io
import logging
import os
import time

import pytest
from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.plugins.terminology.models.autoterm import TerminologyModel

GOOD_PO = b'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Bonjour"
'''

# A captive-portal/signon page: served with a normal 200 status, but
# not the terminology file it claims to be.
SIGNON_PAGE = b'<html><body>Please log in to continue</body></html>'


class _FakeRequest:
    status = 200

    def __init__(self, headers=b'ETag: "abc123"\r\n', effective_url='http://example.com/en__fr.po'):
        self.result_headers = io.BytesIO(headers)
        self._effective_url = effective_url

    def get_effective_url(self):
        return self._effective_url


class _FakeClient:
    """Records what init_matcher()/get() was actually asked for, without
    a real network request."""

    def __init__(self):
        self.calls = []

    def get(self, url, callback, etag, error_callback=None, download=False):
        self.calls.append(dict(url=url, callback=callback, etag=etag,
                                error_callback=error_callback, download=download))


def _fake_self():
    fake_self = TerminologyModel.__new__(TerminologyModel)
    fake_self.config = {}
    fake_self.matcher = None
    return fake_self


@pytest.fixture(autouse=True)
def _isolate_terminology_matchers():
    """init_matcher() mutates the real, shared
    TerminologyPlaceable.matchers class-level list - restore it so a
    matcher left over from one test never leaks into the next."""
    before = list(TerminologyPlaceable.matchers)
    yield
    TerminologyPlaceable.matchers[:] = before


@pytest.fixture(autouse=True)
def _isolate_termdir(tmp_path, monkeypatch):
    """TERMDIR is a real class attribute pointing at the user's actual
    config directory (~/.virtaal/autoterm or platform equivalent) -
    patch it here, once, for every test in this file, rather than
    trusting each test to set fake_self.TERMDIR itself. A test that
    forgot used to fall back to the real ambient directory instead of
    failing loudly - harmless read-only locally where that directory
    already exists, but a FileNotFoundError on a fresh CI runner."""
    monkeypatch.setattr(TerminologyModel, 'TERMDIR', str(tmp_path))


def test_process_header_saves_a_parseable_response(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')

    TerminologyModel._process_header(fake_self, _FakeRequest(), GOOD_PO, localfile=localfile)

    assert os.path.isfile(localfile)
    assert open(localfile, 'rb').read() == GOOD_PO


def test_process_header_discards_an_unparseable_response(tmp_path):
    # #1503: a signon network's login page used to get saved and
    # cached as if it were the real terminology file.
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')

    TerminologyModel._process_header(fake_self, _FakeRequest(), SIGNON_PAGE, localfile=localfile)

    assert not os.path.isfile(localfile)
    assert fake_self.config == {}


def test_process_header_keeps_a_previously_cached_file_on_bad_response(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')
    open(localfile, 'wb').write(GOOD_PO)

    TerminologyModel._process_header(fake_self, _FakeRequest(), SIGNON_PAGE, localfile=localfile)

    assert open(localfile, 'rb').read() == GOOD_PO


def test_process_header_a_304_leaves_an_existing_file_untouched(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')
    open(localfile, 'wb').write(GOOD_PO)
    request = _FakeRequest()
    request.status = 304

    TerminologyModel._process_header(fake_self, request, b'', localfile=localfile)

    assert open(localfile, 'rb').read() == GOOD_PO


def test_process_header_with_no_localfile_derives_the_name_from_the_url(tmp_path):
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = 'fr'

    TerminologyModel._process_header(fake_self, _FakeRequest(effective_url='http://x/terms.po'), GOOD_PO, localfile=None)

    assert open(os.path.join(str(tmp_path), 'en__fr.po'), 'rb').read() == GOOD_PO


def test_process_header_with_no_extension_in_the_url_guesses_from_content(tmp_path):
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = 'fr'

    TerminologyModel._process_header(fake_self, _FakeRequest(effective_url='http://x/download'), GOOD_PO, localfile=None)

    assert open(os.path.join(str(tmp_path), 'en__fr.po'), 'rb').read() == GOOD_PO


def test_process_header_defaults_to_po_when_nothing_can_be_guessed(tmp_path):
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = 'fr'
    garbage = b'not a translation file at all, just plain garbage'

    TerminologyModel._process_header(fake_self, _FakeRequest(effective_url='http://x/download'), garbage, localfile=None)

    # _parses_as() rejects it before a file ever gets written, but the
    # ext-guessing still had to fall all the way through to the 'po'
    # default first - exercised via init_matcher() not raising.
    assert not os.listdir(str(tmp_path))


def test_process_header_saves_the_etag_from_the_response_headers(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')

    TerminologyModel._process_header(fake_self, _FakeRequest(headers=b'ETag: "abc123"\r\n'), GOOD_PO, localfile=localfile)

    assert fake_self.config[os.path.abspath(localfile)] == 'abc123'


def test_process_header_an_unhandled_status_resets_the_matcher(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')
    open(localfile, 'wb').write(GOOD_PO)
    request = _FakeRequest()
    request.status = 404

    TerminologyModel._process_header(fake_self, request, b'', localfile=localfile)

    # The file on disk is untouched, but the matcher was rebuilt from
    # an empty store (localfile treated as '' for this response).
    assert open(localfile, 'rb').read() == GOOD_PO
    assert fake_self.store.getunits() == []


# init_matcher() #

def test_init_matcher_with_no_file_builds_an_empty_store():
    fake_self = _fake_self()

    TerminologyModel.init_matcher(fake_self, '')

    assert fake_self.store.getunits() == []
    assert fake_self.matcher in TerminologyPlaceable.matchers


def test_init_matcher_with_a_real_file_loads_it(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')
    open(localfile, 'wb').write(GOOD_PO)

    TerminologyModel.init_matcher(fake_self, localfile)

    assert [u.target for u in fake_self.store.getunits() if u.source == 'Hello'] == ['Bonjour']


def test_init_matcher_removes_the_previous_matcher_first():
    fake_self = _fake_self()
    TerminologyModel.init_matcher(fake_self, '')
    first_matcher = fake_self.matcher
    assert first_matcher in TerminologyPlaceable.matchers

    TerminologyModel.init_matcher(fake_self, '')

    assert first_matcher not in TerminologyPlaceable.matchers
    assert fake_self.matcher in TerminologyPlaceable.matchers


# _get_curr_term_filename() #

def test_get_curr_term_filename_defaults_to_the_instances_own_languages():
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = 'fr'

    assert TerminologyModel._get_curr_term_filename(fake_self) == 'en__fr.po'


def test_get_curr_term_filename_finds_an_existing_file_regardless_of_extension(tmp_path):
    fake_self = _fake_self()
    open(os.path.join(str(tmp_path), 'en__fr.tbx'), 'w').close()

    assert TerminologyModel._get_curr_term_filename(fake_self, 'en', 'fr') == 'en__fr.tbx'


def test_get_curr_term_filename_falls_back_to_po_when_nothing_exists():
    fake_self = _fake_self()

    assert TerminologyModel._get_curr_term_filename(fake_self, 'en', 'fr') == 'en__fr.po'


# is_update_needed() #

def test_is_update_needed_is_true_when_no_local_file_exists():
    fake_self = _fake_self()

    assert TerminologyModel.is_update_needed(fake_self, 'en', 'fr') is True


def test_is_update_needed_is_false_for_a_fresh_file(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')
    open(localfile, 'w').close()

    assert TerminologyModel.is_update_needed(fake_self, 'en', 'fr') is False


def test_is_update_needed_is_true_for_a_stale_file(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')
    open(localfile, 'w').close()
    four_days_ago = time.time() - 60 * 60 * 24 * 4
    os.utime(localfile, (four_days_ago, four_days_ago))

    assert TerminologyModel.is_update_needed(fake_self, 'en', 'fr') is True


# update_terms() #

def test_update_terms_with_neither_language_is_a_noop(monkeypatch):
    fake_self = _fake_self()
    fake_self.source_lang = None
    fake_self.target_lang = None
    monkeypatch.setattr(fake_self, 'is_update_needed', lambda *a: pytest.fail('should not be called'))

    TerminologyModel.update_terms(fake_self)  # must not raise


def test_update_terms_with_only_one_language_raises():
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = None

    with pytest.raises(ValueError):
        TerminologyModel.update_terms(fake_self)


def test_update_terms_skips_the_download_when_not_needed(monkeypatch, tmp_path):
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = 'fr'
    open(os.path.join(str(tmp_path), 'en__fr.po'), 'w').close()
    calls = []
    monkeypatch.setattr(fake_self, 'init_matcher', lambda f: calls.append(f))

    TerminologyModel.update_terms(fake_self, 'en', 'fr')

    assert calls == [os.path.join(str(tmp_path), 'en__fr.po')]


def test_update_terms_downloads_when_needed(monkeypatch, tmp_path):
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = 'fr'
    calls = []
    monkeypatch.setattr(fake_self, '_update_term_file', lambda s, t: calls.append((s, t)))

    TerminologyModel.update_terms(fake_self, 'en', 'fr')

    assert calls == [('en', 'fr')]


# _check_for_update() #

def test_check_for_update_sends_a_known_etag(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')
    open(localfile, 'w').close()
    fake_self.config = {os.path.abspath(localfile): '"abc123"'}
    fake_self.client = _FakeClient()

    TerminologyModel._check_for_update(fake_self, 'en', 'fr')

    [call] = fake_self.client.calls
    assert call['etag'] == '"abc123"'
    assert call['download'] is True
    assert call['error_callback'] is None


def test_check_for_update_passes_none_as_localfile_when_nothing_cached(tmp_path):
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = 'fr'
    fake_self.client = _FakeClient()

    TerminologyModel._check_for_update(fake_self, 'en', 'fr')

    [call] = fake_self.client.calls
    assert call['etag'] is None
    request = _FakeRequest()
    call['callback'](request, GOOD_PO)  # must not raise - localfile=None path
    assert open(os.path.join(str(tmp_path), 'en__fr.po'), 'rb').read() == GOOD_PO


def test_check_for_update_adds_an_error_callback_at_debug_level(monkeypatch):
    fake_self = _fake_self()
    fake_self.client = _FakeClient()
    monkeypatch.setattr(logging.root, 'level', logging.DEBUG)

    TerminologyModel._check_for_update(fake_self, 'en', 'fr')

    [call] = fake_self.client.calls
    assert call['error_callback'] is not None
    call['error_callback'](_FakeRequest(), None)  # must not raise


# _get_ext_from_url() #

def test_get_ext_from_url_extracts_the_extension():
    fake_self = _fake_self()

    assert TerminologyModel._get_ext_from_url(fake_self, 'http://example.com/terms.tbx') == 'tbx'


def test_get_ext_from_url_returns_none_without_a_filename():
    fake_self = _fake_self()

    assert TerminologyModel._get_ext_from_url(fake_self, 'http://example.com/') is None


def test_get_ext_from_url_returns_none_without_an_extension():
    fake_self = _fake_self()

    assert TerminologyModel._get_ext_from_url(fake_self, 'http://example.com/download') is None


def test_get_ext_from_url_returns_none_for_a_trailing_dot_with_nothing_after_it():
    fake_self = _fake_self()

    assert TerminologyModel._get_ext_from_url(fake_self, 'http://example.com/terms.') is None


# _get_ext_from_store_guess() #

def test_get_ext_from_store_guess_recognises_a_real_po_file():
    fake_self = _fake_self()

    assert TerminologyModel._get_ext_from_store_guess(fake_self, GOOD_PO) == 'po'


def test_get_ext_from_store_guess_returns_none_for_unrecognisable_content():
    fake_self = _fake_self()

    assert TerminologyModel._get_ext_from_store_guess(fake_self, b'plain garbage') is None


# _update_term_file() #

def test_update_term_file_resets_the_matcher_before_checking_for_an_update(monkeypatch):
    fake_self = _fake_self()
    calls = []
    monkeypatch.setattr(fake_self, 'init_matcher', lambda: calls.append('init_matcher'))
    monkeypatch.setattr(fake_self, '_check_for_update', lambda s, t: calls.append(('_check_for_update', s, t)))

    TerminologyModel._update_term_file(fake_self, 'en', 'fr')

    assert calls == ['init_matcher', ('_check_for_update', 'en', 'fr')]


# _on_lang_changed() #

def test_on_lang_changed_updates_the_attribute_and_refreshes_terms(monkeypatch):
    fake_self = _fake_self()
    fake_self.source_lang = 'en'
    fake_self.target_lang = 'de'
    calls = []
    monkeypatch.setattr(fake_self, 'update_terms', lambda s, t: calls.append((s, t)))

    TerminologyModel._on_lang_changed(fake_self, lang_controller=None, lang='fr', which='target')

    assert fake_self.target_lang == 'fr'
    assert calls == [('en', 'fr')]
