#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import GObject

from virtaal.plugins.tm.models.remotetm import TMModel, unit2dict


def _model(source_lang='en', target_lang='af', checker=None, cache=None):
    model = TMModel.__new__(TMModel)
    GObject.GObject.__init__(model)
    model.source_lang = source_lang
    model.target_lang = target_lang
    model.checker = checker
    model.cache = cache if cache is not None else {}
    model.shortname = 'Remote TM'
    return model


def _unit(source='hello'):
    return SimpleNamespace(source=source)


# query()

def test_query_does_nothing_when_source_and_target_languages_match():
    model = _model(source_lang='en', target_lang='en')
    model.tmclient = SimpleNamespace(translate_unit=lambda *a: (_ for _ in ()).throw(
        AssertionError('should not query with a misconfigured en->en pair')))
    matches = []
    model.connect('match-found', lambda m, q, r: matches.append((q, r)))

    model.query(None, _unit('hello'))

    assert matches == []


def test_query_emits_a_cached_match_without_calling_the_client():
    model = _model(cache={'hello': [{'target': 'Hallo'}]})
    model.tmclient = SimpleNamespace(translate_unit=lambda *a: (_ for _ in ()).throw(
        AssertionError('should use the cache')))
    matches = []
    model.connect('match-found', lambda m, q, r: matches.append((q, r)))

    model.query(None, _unit('hello'))

    assert matches == [('hello', [{'target': 'Hallo'}])]


def test_query_emits_nothing_for_a_cached_negative_result():
    model = _model(cache={'hello': None})
    model.tmclient = SimpleNamespace(translate_unit=lambda *a: (_ for _ in ()).throw(
        AssertionError('should use the cache')))
    matches = []
    model.connect('match-found', lambda m, q, r: matches.append((q, r)))

    model.query(None, _unit('hello'))

    assert matches == []


def test_query_asks_the_tmclient_when_not_cached():
    calls = []
    model = _model()
    model.tmclient = SimpleNamespace(translate_unit=lambda *a: calls.append(a))

    model.query(None, _unit('hello'))

    (query_str, source_lang, target_lang, callback, params) = calls[0]
    assert (query_str, source_lang, target_lang) == ('hello', 'en', 'af')
    assert callback == model._handle_matches
    assert params == {}


def test_query_includes_the_checker_style_when_set():
    calls = []
    model = _model(checker='standard')
    model.tmclient = SimpleNamespace(translate_unit=lambda *a: calls.append(a))

    model.query(None, _unit('hello'))

    assert calls[0][4] == {'style': 'standard'}


# _handle_matches()

def test_handle_matches_caches_none_and_emits_nothing_when_there_are_no_matches():
    model = _model()
    matches = []
    model.connect('match-found', lambda m, q, r: matches.append((q, r)))

    model._handle_matches(None, 'hello', [])

    assert model.cache['hello'] is None
    assert matches == []


def test_handle_matches_labels_each_match_then_emits():
    model = _model()
    emitted = []
    model.connect('match-found', lambda m, q, r: emitted.append((q, r)))
    raw_matches = [{'target': 'Hallo', 'source': 'hello'}]

    model._handle_matches(None, 'hello', raw_matches)

    assert model.cache['hello'] == raw_matches
    assert raw_matches[0]['target'] == 'Hallo'
    assert raw_matches[0]['tmsource'] == 'Remote TM'
    assert emitted == [('hello', raw_matches)]


# push_store() / upload_store()

def test_push_store_only_sends_translated_units():
    added = []
    model = _model()
    model.tmclient = SimpleNamespace(add_store=lambda *a: added.append(a))
    translated = SimpleNamespace(source='hello', target='Hallo', getcontext=lambda: '', istranslated=lambda: True)
    untranslated = SimpleNamespace(source='bye', target='', getcontext=lambda: '', istranslated=lambda: False)
    store_controller = SimpleNamespace(store=SimpleNamespace(
        get_units=lambda: [translated, untranslated], get_filename=lambda: 'file.po'))

    model.push_store(store_controller)

    (filename, units, source_lang, target_lang) = added[0]
    assert filename == 'file.po'
    assert units == [{'source': 'hello', 'target': 'Hallo', 'context': ''}]
    assert (source_lang, target_lang) == ('en', 'af')


def test_push_store_resets_the_cache():
    model = _model(cache={'stale': 'entry'})
    model.tmclient = SimpleNamespace(add_store=lambda *a: None)
    store_controller = SimpleNamespace(store=SimpleNamespace(get_units=lambda: [], get_filename=lambda: 'file.po'))

    model.push_store(store_controller)

    assert model.cache == {}


def test_upload_store_resets_the_cache():
    model = _model(cache={'stale': 'entry'})
    model.tmclient = SimpleNamespace(upload_store=lambda *a: None)
    store_controller = SimpleNamespace(store=SimpleNamespace(_trans_store='store'))

    model.upload_store(store_controller)

    assert model.cache == {}


def test_unit2dict_extracts_the_relevant_fields():
    unit = SimpleNamespace(source='hello', target='Hallo', getcontext=lambda: 'greeting')

    assert unit2dict(unit) == {'source': 'hello', 'target': 'Hallo', 'context': 'greeting'}
