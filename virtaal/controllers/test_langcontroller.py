#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.controllers import langcontroller
from virtaal.controllers.langcontroller import LanguageController
from virtaal.models.langmodel import LanguageModel


class _FakeSettings:
    def __init__(self, sourcelang='en', targetlang='af', recentlangs=''):
        self.language = {
            'sourcelang': sourcelang,
            'targetlang': targetlang,
            'recentlangs': recentlangs,
        }


class _FakeSignalSource:
    def __init__(self):
        self.connected = []

    def connect(self, signal, handler):
        self.connected.append((signal, handler))
        return len(self.connected)


def _make_main_controller():
    main_controller = _FakeSignalSource()
    main_controller.store_controller = _FakeSignalSource()
    return main_controller


def _make_controller(monkeypatch, tmp_path, settings=None):
    monkeypatch.setattr(langcontroller.pan_app, 'settings', settings or _FakeSettings())
    monkeypatch.setattr(langcontroller.pan_app, 'get_config_dir', lambda: str(tmp_path))
    main_controller = _make_main_controller()
    controller = LanguageController(main_controller)
    return controller, main_controller


def test_init_wires_the_store_loaded_and_quit_signals(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)

    assert main_controller.lang_controller is controller
    assert controller.view is None
    assert ('quit', controller._on_quit) in main_controller.connected
    assert ('store-loaded', controller._on_store_loaded) in main_controller.store_controller.connected


def test_init_loads_the_configured_source_and_target_langs(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path, _FakeSettings(sourcelang='fr', targetlang='de'))

    assert controller.source_lang.code == 'fr'
    assert controller.target_lang.code == 'de'


class _MissingLangSettings:
    # pan_app.settings.language missing the sourcelang/targetlang keys -
    # the realistic way _init_langs()'s except branches trigger, since
    # LanguageModel() itself never raises (unknown codes just fall back).
    language = {'recentlangs': ''}


def test_init_langs_falls_back_to_none_when_settings_are_unreadable(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path, _MissingLangSettings())

    assert controller.source_lang is None
    assert controller.target_lang is None


def test_init_loads_previously_saved_new_languages(monkeypatch, tmp_path):
    (tmp_path / 'langs.ini').write_text(
        '[xx-saved]\nname = Saved Lang\nnplurals = 3\nplural = n>1\n'
    )
    try:
        controller, _ = _make_controller(monkeypatch, tmp_path)

        assert LanguageModel.languages['xx-saved'] == ('Saved Lang', 3, 'n>1')
    finally:
        LanguageModel.languages.pop('xx-saved', None)


def test_load_recent_parses_saved_pairs(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path, _FakeSettings(recentlangs='en,af|fr,de'))

    assert [(s.code, t.code) for s, t in controller.recent_pairs] == [('en', 'af'), ('fr', 'de')]


def test_load_recent_is_empty_when_nothing_saved(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path, _FakeSettings(recentlangs=''))

    assert controller.recent_pairs == []


def test_source_lang_setter_converts_a_string_to_a_language_model(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    calls = []
    controller.connect('source-lang-changed', lambda c, code: calls.append(code))

    controller.source_lang = 'fr'

    assert controller.source_lang.code == 'fr'
    assert calls == ['fr']


def test_source_lang_setter_ignores_none(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path, _FakeSettings(sourcelang='en'))
    calls = []
    controller.connect('source-lang-changed', lambda c, code: calls.append(code))

    controller.source_lang = None

    assert controller.source_lang.code == 'en'
    assert calls == []


def test_source_lang_setter_ignores_an_unchanged_language(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path, _FakeSettings(sourcelang='en'))
    calls = []
    controller.connect('source-lang-changed', lambda c, code: calls.append(code))

    controller.source_lang = 'en'

    assert calls == []


def test_target_lang_setter_converts_a_string_to_a_language_model(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    calls = []
    controller.connect('target-lang-changed', lambda c, code: calls.append(code))

    controller.target_lang = 'de'

    assert controller.target_lang.code == 'de'
    assert calls == ['de']


def _view_stub():
    # source_lang/target_lang's setters emit signals connected to
    # _on_lang_changed(), which itself calls notify_same_langs()/
    # notify_diff_langs() - both are needed even when a test only
    # cares about set_language_pair()'s own explicit notification.
    return SimpleNamespace(
        update_recent_pairs=lambda: None,
        notify_same_langs=lambda: None,
        notify_diff_langs=lambda: None,
    )


def test_set_language_pair_dedupes_and_moves_the_pair_to_front(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    controller.view = _view_stub()
    controller.recent_pairs = [(LanguageModel('fr'), LanguageModel('af'))]

    controller.set_language_pair('fr', 'af')

    assert len(controller.recent_pairs) == 1
    assert controller.recent_pairs[0][0].code == 'fr'
    assert controller.recent_pairs[0][1].code == 'af'


def test_set_language_pair_truncates_to_num_recent(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    controller.view = _view_stub()
    controller.recent_pairs = [
        (LanguageModel(f'src{i}'), LanguageModel(f'tgt{i}')) for i in range(LanguageController.NUM_RECENT)
    ]

    controller.set_language_pair('newsrc', 'newtgt')

    assert len(controller.recent_pairs) == LanguageController.NUM_RECENT
    assert controller.recent_pairs[0][0].code == 'newsrc'


def test_set_language_pair_notifies_same_langs_when_equal(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    calls = []
    controller.view = SimpleNamespace(
        update_recent_pairs=lambda: calls.append('update'),
        notify_same_langs=lambda: calls.append('same'),
        notify_diff_langs=lambda: calls.append('diff'),
    )

    controller.set_language_pair('fr', 'fr')

    # The trailing pair is set_language_pair()'s own explicit check;
    # source_lang/target_lang's setters also notify along the way as
    # each one changes in turn (see _view_stub()).
    assert calls[-2:] == ['update', 'same']


def test_set_language_pair_does_not_notify_when_different(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    calls = []
    controller.view = SimpleNamespace(
        update_recent_pairs=lambda: calls.append('update'),
        notify_same_langs=lambda: calls.append('same'),
        notify_diff_langs=lambda: calls.append('diff'),
    )

    controller.set_language_pair('fr', 'af')

    assert calls[-1] == 'update'


def test_get_detected_langs_returns_none_without_a_store(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    main_controller.store_controller.store = None

    assert controller.get_detected_langs() is None


class _FakeIdentifier:
    def identify_source_lang(self, units):
        return 'fr'

    def identify_target_lang(self, units):
        return 'af'


def test_get_detected_langs_builds_language_models_from_identified_codes(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    main_controller.store_controller.store = SimpleNamespace(get_units=lambda: [])
    monkeypatch.setattr('translate.lang.identify.LanguageIdentifier', _FakeIdentifier)

    srclang, tgtlang = controller.get_detected_langs()

    assert srclang.code == 'fr'
    assert tgtlang.code == 'af'


class _FakeUnidentifiableIdentifier:
    def identify_source_lang(self, units):
        return None

    def identify_target_lang(self, units):
        return None


def test_get_detected_langs_returns_none_for_unidentified_codes(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    main_controller.store_controller.store = SimpleNamespace(get_units=lambda: [])
    monkeypatch.setattr('translate.lang.identify.LanguageIdentifier', _FakeUnidentifiableIdentifier)

    srclang, tgtlang = controller.get_detected_langs()

    assert srclang is None
    assert tgtlang is None


def test_save_recent_serializes_pairs_to_settings(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    controller.recent_pairs = [
        (LanguageModel('en'), LanguageModel('af')),
        (LanguageModel('fr'), LanguageModel('de')),
    ]

    controller.save_recent()

    assert langcontroller.pan_app.settings.language['recentlangs'] == 'en,af|fr,de'


def test_on_lang_changed_saves_and_notifies_same_langs(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    controller._source_lang = LanguageModel('en')
    controller._target_lang = LanguageModel('en')
    save_calls = []
    monkeypatch.setattr(controller, 'save_recent', lambda: save_calls.append(True))
    notify_calls = []
    controller.view = SimpleNamespace(
        notify_same_langs=lambda: notify_calls.append('same'),
        notify_diff_langs=lambda: notify_calls.append('diff'),
    )

    controller._on_lang_changed(controller, 'en')

    assert save_calls == [True]
    assert notify_calls == ['same']


def test_on_lang_changed_notifies_diff_langs_when_languages_differ(monkeypatch, tmp_path):
    controller, _ = _make_controller(monkeypatch, tmp_path)
    controller._source_lang = LanguageModel('en')
    controller._target_lang = LanguageModel('af')
    monkeypatch.setattr(controller, 'save_recent', lambda: None)
    notify_calls = []
    controller.view = SimpleNamespace(
        notify_same_langs=lambda: notify_calls.append('same'),
        notify_diff_langs=lambda: notify_calls.append('diff'),
    )

    controller._on_lang_changed(controller, 'af')

    assert notify_calls == ['diff']


def test_on_quit_saves_the_current_languages(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    controller._source_lang = LanguageModel('en')
    controller._target_lang = LanguageModel('af')
    controller.new_langs = []

    controller._on_quit(main_controller)

    assert langcontroller.pan_app.settings.language['sourcelang'] == 'en'
    assert langcontroller.pan_app.settings.language['targetlang'] == 'af'


def test_on_quit_writes_new_languages_to_langs_ini(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    controller._source_lang = LanguageModel('en')
    controller._target_lang = LanguageModel('af')
    LanguageModel.languages['xx-new'] = ('Xx Lang', 3, 'n>1')
    controller.new_langs = ['xx-new']
    try:
        controller._on_quit(main_controller)

        saved = langcontroller.pan_app.load_config(str(tmp_path / 'langs.ini'))
        assert saved['xx-new']['name'] == 'Xx Lang'
        assert saved['xx-new']['nplurals'] == '3'
        assert saved['xx-new']['plural'] == 'n>1'
    finally:
        LanguageModel.languages.pop('xx-new', None)


def test_on_quit_merges_with_an_existing_langs_ini(monkeypatch, tmp_path):
    (tmp_path / 'langs.ini').write_text(
        '[xx-old]\nname = Old Lang\nnplurals = 2\nplural = n != 1\n'
    )
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    controller._source_lang = LanguageModel('en')
    controller._target_lang = LanguageModel('af')
    LanguageModel.languages['xx-new2'] = ('Xx New', 1, '0')
    controller.new_langs = ['xx-new2']
    try:
        controller._on_quit(main_controller)

        saved = langcontroller.pan_app.load_config(str(tmp_path / 'langs.ini'))
        assert 'xx-old' in saved
        assert 'xx-new2' in saved
    finally:
        LanguageModel.languages.pop('xx-new2', None)


def test_on_quit_does_nothing_further_without_new_langs(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    controller._source_lang = LanguageModel('en')
    controller._target_lang = LanguageModel('af')
    controller.new_langs = []

    controller._on_quit(main_controller)

    assert not (tmp_path / 'langs.ini').exists()


class _FakeLanguageView:
    def __init__(self, controller):
        self.controller = controller
        self.shown = False

    def show(self):
        self.shown = True

    def update_recent_pairs(self):
        pass

    def notify_same_langs(self):
        pass

    def notify_diff_langs(self):
        pass


def test_on_store_loaded_creates_the_view_and_sets_the_language_pair(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    created = []
    monkeypatch.setattr('virtaal.views.langview.LanguageView',
                         lambda c: created.append(c) or _FakeLanguageView(c))
    main_controller.store_controller.store = SimpleNamespace(
        get_source_language=lambda: 'fr',
        get_target_language=lambda: 'zzunknown',
    )
    main_controller.store_controller.get_nplurals = lambda: 4

    controller._on_store_loaded(main_controller.store_controller)

    assert created == [controller]
    assert controller.view.shown
    assert controller.source_lang.code == 'fr'
    assert controller.target_lang.code == 'zzunknown'
    assert controller.target_lang.nplurals == 4


def test_on_store_loaded_reuses_an_existing_view(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path)
    controller.view = _view_stub()
    created = []
    monkeypatch.setattr('virtaal.views.langview.LanguageView', lambda c: created.append(c))
    main_controller.store_controller.store = SimpleNamespace(
        get_source_language=lambda: 'en',
        get_target_language=lambda: 'af',
    )
    main_controller.store_controller.get_nplurals = lambda: 2

    controller._on_store_loaded(main_controller.store_controller)

    assert created == []


def test_on_store_loaded_falls_back_to_the_current_source_lang(monkeypatch, tmp_path):
    controller, main_controller = _make_controller(monkeypatch, tmp_path, _FakeSettings(sourcelang='en'))
    controller.view = _view_stub()
    main_controller.store_controller.store = SimpleNamespace(
        get_source_language=lambda: None,
        get_target_language=lambda: 'af',
    )
    main_controller.store_controller.get_nplurals = lambda: 2

    controller._on_store_loaded(main_controller.store_controller)

    assert controller.source_lang.code == 'en'
