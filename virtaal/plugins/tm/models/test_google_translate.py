#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import json
from types import SimpleNamespace

from gi.repository import GObject

from virtaal.plugins.tm.models import google_translate
from virtaal.plugins.tm.models.google_translate import TMModel


def _model():
    model = TMModel.__new__(TMModel)
    GObject.GObject.__init__(model)
    model.source_lang = 'en'
    model.target_lang = 'af'
    model.cache = {}
    model._languages = {'en', 'af'}
    model.config = {'api_key': 'test-key'}
    return model


# __init__(): with an API key configured, the languages-list request
# must actually build from languages_url (url_getlanguages doesn't
# exist - a plain AttributeError on every real launch with a key set).

class _FakeHTTPClient:
    def __init__(self):
        self.added = []

    def add(self, request):
        self.added.append(request)


def _fake_controller():
    connectable = lambda: SimpleNamespace(connect=lambda signal, handler, *a: 1)
    lang_controller = connectable()
    lang_controller.source_lang = SimpleNamespace(code='en')
    lang_controller.target_lang = SimpleNamespace(code='af')
    checks_controller = connectable()
    checks_controller.code = 'standard'
    main_controller = SimpleNamespace(lang_controller=lang_controller, checks_controller=checks_controller)
    controller = connectable()
    controller.main_controller = main_controller
    return controller


def test_init_builds_the_languages_request_from_languages_url(monkeypatch):
    monkeypatch.setattr(google_translate, 'HTTPClient', _FakeHTTPClient)
    monkeypatch.setattr(TMModel, 'load_config', lambda self: setattr(self, 'config', {'api_key': 'test-key'}))

    model = TMModel('google_translate', _fake_controller())

    assert len(model.client.added) == 1
    assert model.client.added[0].url == model.languages_url % {'key': 'test-key'}


# _disable_all()

def test_disable_all_clears_the_language_set():
    model = _model()

    model._disable_all('some reason')

    assert model._languages == set()


# query()

def test_query_truncates_a_source_string_that_exceeds_googles_url_limit():
    # Google's Terms of Service caps the whole URL at 2000 characters.
    from urllib.parse import unquote_plus
    added = []
    model = _model()
    model.client = SimpleNamespace(add=lambda req: added.append(req))
    long_source = 'x' * 3000

    model.query(None, SimpleNamespace(source=long_source))

    query_param = added[0].url.split('q=')[1].split('&')[0]
    assert len(unquote_plus(query_param)) == 2000 - len(model.translate_url)


def test_query_translates_language_codes_before_checking_support():
    model = _model()
    model._languages = {'iw', 'af'}  # Google's own code for Hebrew
    model.source_lang = 'he'
    model.client = SimpleNamespace(add=lambda req: None)

    model.query(None, SimpleNamespace(source='hello'))  # must not raise (he -> iw is supported)


def test_query_replaces_underscore_with_hyphen_in_region_codes():
    model = _model()
    model._languages = {'en', 'pt-BR'}
    model.target_lang = 'pt_BR'
    added = []
    model.client = SimpleNamespace(add=lambda req: added.append(req))

    model.query(None, SimpleNamespace(source='hello'))

    assert len(added) == 1
    assert 'target=pt-BR' in added[0].url


def test_query_does_nothing_for_an_unsupported_language_pair():
    model = _model()
    model._languages = {'fr', 'de'}
    model.client = SimpleNamespace(add=lambda req: (_ for _ in ()).throw(
        AssertionError('should not query an unsupported pair')))

    model.query(None, SimpleNamespace(source='hello'))  # must not raise


def test_query_emits_a_cached_match():
    model = _model()
    model.cache = {'hello': [{'target': 'Hallo'}]}
    model.client = SimpleNamespace(add=lambda req: (_ for _ in ()).throw(
        AssertionError('should use the cache')))
    emitted = []
    model.connect('match-found', lambda m, q, r: emitted.append((q, r)))

    model.query(None, SimpleNamespace(source='hello'))

    assert emitted == [('hello', [{'target': 'Hallo'}])]


def test_query_sends_a_translate_request_for_an_uncached_pair():
    added = []
    model = _model()
    model.client = SimpleNamespace(add=lambda req: added.append(req))

    model.query(None, SimpleNamespace(source='hello'))

    assert len(added) == 1
    assert 'key=test-key' in added[0].url
    assert 'source=en' in added[0].url
    assert 'target=af' in added[0].url


# got_translation()

def test_got_translation_emits_a_match_on_success():
    model = _model()
    emitted = []
    model.connect('match-found', lambda m, q, r: emitted.append((q, r)))
    response = json.dumps({'data': {'translations': [{'translatedText': 'Hallo'}]}})

    model.got_translation(response, 'hello')

    assert model.cache['hello'] == [{'source': 'hello', 'target': 'Hallo', 'tmsource': 'Google'}]
    assert emitted == [('hello', model.cache['hello'])]


def test_got_translation_unescapes_html_entities():
    model = _model()
    response = json.dumps({'data': {'translations': [{'translatedText': 'Tom &amp; Jerry'}]}})

    model.got_translation(response, 'Tom & Jerry')

    assert model.cache['Tom & Jerry'][0]['target'] == 'Tom & Jerry'


def test_got_translation_disables_all_queries_on_a_malformed_response():
    model = _model()

    model.got_translation('not json at all', 'hello')

    assert model._languages == set()
    assert model.cache == {}


def test_got_translation_disables_all_queries_on_an_unexpected_shape():
    model = _model()

    model.got_translation(json.dumps({'unexpected': 'shape'}), 'hello')

    assert model._languages == set()


# got_languages()

def test_got_languages_populates_the_language_set():
    model = _model()
    model._languages = set()
    response = json.dumps({'data': {'languages': [{'language': 'en'}, {'language': 'af'}]}})

    model.got_languages(response)

    assert model._languages == {'en', 'af'}


def test_got_languages_disables_all_on_a_malformed_response():
    model = _model()

    model.got_languages('not json at all')

    assert model._languages == set()


# got_error()

def test_got_error_disables_all_queries():
    model = _model()

    model.got_error('500 server error', 'hello')

    assert model._languages == set()
