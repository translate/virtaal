#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import json
import logging
from types import SimpleNamespace

from gi.repository import GObject

from virtaal.plugins.tm.models.apertium import TMModel


def _model():
    model = TMModel.__new__(TMModel)
    GObject.GObject.__init__(model)
    model.source_lang = 'en'
    model.target_lang = 'af'
    model.cache = {}
    model.language_pairs = [('en', 'af')]
    model.url_translate = 'https://www.apertium.org/apy/translate'
    return model


# got_language_pairs()

def test_got_language_pairs_stores_the_pairs_on_success():
    model = _model()
    model.language_pairs = []
    response = json.dumps({
        'responseStatus': 200,
        'responseData': [
            {'sourceLanguage': 'en', 'targetLanguage': 'af'},
            {'sourceLanguage': 'af', 'targetLanguage': 'en'},
        ],
    })

    model.got_language_pairs(response)

    assert model.language_pairs == [('en', 'af'), ('af', 'en')]


def test_got_language_pairs_ignores_a_non_200_response():
    model = _model()
    model.language_pairs = []
    response = json.dumps({'responseStatus': 500, 'responseDetails': 'boom'})

    model.got_language_pairs(response)

    assert model.language_pairs == []


# query()

def test_query_does_nothing_for_an_unsupported_language_pair():
    model = _model()
    model.language_pairs = [('fr', 'de')]
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
    assert 'langpair=en%7Caf' in added[0].url


# got_translation()

def test_got_translation_emits_a_match_on_success():
    model = _model()
    emitted = []
    model.connect('match-found', lambda m, q, r: emitted.append((q, r)))
    response = json.dumps({'responseStatus': 200, 'responseData': {'translatedText': 'Hallo'}})

    model.got_translation(response, 'hello')

    assert model.cache['hello'] == [{'source': 'hello', 'target': 'Hallo', 'tmsource': 'Apertium'}]
    assert emitted == [('hello', model.cache['hello'])]


def test_got_translation_strips_a_trailing_newline_the_query_did_not_have():
    model = _model()
    response = json.dumps({'responseStatus': 200, 'responseData': {'translatedText': 'Hallo\n'}})

    model.got_translation(response, 'hello')

    assert model.cache['hello'][0]['target'] == 'Hallo'


def test_got_translation_keeps_a_trailing_newline_the_query_also_had():
    model = _model()
    response = json.dumps({'responseStatus': 200, 'responseData': {'translatedText': 'Hallo\n'}})

    model.got_translation(response, 'hello\n')

    assert model.cache['hello\n'][0]['target'] == 'Hallo\n'


def test_got_translation_unescapes_html_entities():
    model = _model()
    response = json.dumps({'responseStatus': 200, 'responseData': {'translatedText': 'Tom &amp; Jerry'}})

    model.got_translation(response, 'Tom & Jerry')

    assert model.cache['Tom & Jerry'][0]['target'] == 'Tom & Jerry'


def test_got_translation_ignores_a_non_200_response(caplog):
    # Regression: the debug log call here passed (query_str, details) as
    # a single tuple instead of two separate args, so actually
    # formatting the message raised TypeError instead of just logging.
    model = _model()
    response = json.dumps({'responseStatus': 500, 'responseDetails': 'boom'})

    with caplog.at_level(logging.DEBUG):
        model.got_translation(response, 'hello')  # must not raise

    assert model.cache == {}
    assert "Failed to translate 'hello':\nboom" in caplog.text
