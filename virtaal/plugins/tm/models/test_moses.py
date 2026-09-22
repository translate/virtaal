#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import GObject

from virtaal.plugins.tm.models.moses import TMModel


def _model():
    model = TMModel.__new__(TMModel)
    GObject.GObject.__init__(model)
    model.source_lang = None
    model.target_lang = None
    model.cache = {}
    model.clients = {}
    return model


class _FakeMosesClient:
    def __init__(self, server):
        self.server = server
        self.multilang = False
        self.translated = []

    def set_multilang(self):
        self.multilang = True

    def translate_unit(self, query_str, callback, target_lang):
        self.translated.append((query_str, callback, target_lang))


# _init_plugin(): maps "src->tgt" config entries to per-server clients,
# reusing one client (and flagging it multilang) when the same server
# backs more than one language pair. MosesClient itself is imported
# locally inside _init_plugin(), so patch it at its source module.

def _init_plugin(monkeypatch, model, config):
    import virtaal.support.mosesclient as mosesclient_module
    monkeypatch.setattr(mosesclient_module, 'MosesClient', _FakeMosesClient)
    model.config = config
    model._init_plugin()


def test_init_plugin_maps_each_pair_to_a_client(monkeypatch):
    model = _model()
    _init_plugin(monkeypatch, model, {'fr->en': 'http://a'})

    assert model.clients['fr']['en'].server == 'http://a'


def test_init_plugin_reuses_one_client_for_a_shared_server(monkeypatch):
    model = _model()
    _init_plugin(monkeypatch, model, {'fr->en': 'http://a', 'de->en': 'http://a'})

    client_fr = model.clients['fr']['en']
    client_de = model.clients['de']['en']
    assert client_fr is client_de
    assert client_fr.multilang is True


def test_init_plugin_creates_separate_clients_for_different_servers(monkeypatch):
    model = _model()
    _init_plugin(monkeypatch, model, {'fr->en': 'http://a', 'de->en': 'http://b'})

    client_fr = model.clients['fr']['en']
    client_de = model.clients['de']['en']
    assert client_fr is not client_de
    assert client_fr.multilang is False
    assert client_de.multilang is False


# query() / _handle_response()

def test_query_does_nothing_for_an_unconfigured_language_pair():
    model = _model()
    model.source_lang, model.target_lang = 'fr', 'en'

    model.query(None, SimpleNamespace(source='bonjour'))  # must not raise


def test_query_emits_a_cached_match():
    model = _model()
    model.source_lang, model.target_lang = 'fr', 'en'
    model.clients = {'fr': {'en': _FakeMosesClient('http://a')}}
    model.cache = {'bonjour': {'target': 'hello'}}
    emitted = []
    model.connect('match-found', lambda m, q, r: emitted.append((q, r)))

    model.query(None, SimpleNamespace(source='bonjour'))

    assert emitted == [('bonjour', [{'target': 'hello'}])]


def test_query_delegates_to_the_matching_language_pairs_client():
    model = _model()
    model.source_lang, model.target_lang = 'fr', 'en'
    client = _FakeMosesClient('http://a')
    model.clients = {'fr': {'en': client}}

    model.query(None, SimpleNamespace(source='bonjour'))

    assert client.translated == [('bonjour', model._handle_response, 'en')]


def test_handle_response_ignores_an_empty_response():
    model = _model()

    model._handle_response('bonjour', None)  # must not raise

    assert model.cache == {}


def test_handle_response_caches_and_emits_a_translation():
    model = _model()
    emitted = []
    model.connect('match-found', lambda m, q, r: emitted.append((q, r)))

    model._handle_response('bonjour', 'hello')

    assert model.cache['bonjour'] == {'source': 'bonjour', 'target': 'hello', 'tmsource': 'Moses'}
    assert emitted == [('bonjour', [model.cache['bonjour']])]
