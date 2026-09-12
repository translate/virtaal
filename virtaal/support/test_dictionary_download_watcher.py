#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.support.dictionary_download_watcher import DictionaryDownloadWatcher


class _FakeLanguageModel:
    def __init__(self, code):
        self.code = code


class _FakeLangController:
    def __init__(self, target_lang=None):
        self.handlers = {}
        self.target_lang = _FakeLanguageModel(target_lang) if target_lang else None

    def connect(self, signal, handler):
        self.handlers[signal] = handler

    def emit_target_lang_changed(self, language):
        self.handlers['target-lang-changed'](self, language)


class _FakeMainController:
    def __init__(self, target_lang=None):
        self.lang_controller = _FakeLangController(target_lang)


class _FakeEnchant:
    def __init__(self, known_dicts=()):
        self.known_dicts = set(known_dicts)
        self.checked = []

    def dict_exists(self, language):
        self.checked.append(language)
        return language in self.known_dicts

    def list_languages(self):
        return list(self.known_dicts)


class _FakeDownloader:
    instances = []

    def __init__(self, language, on_done=None):
        self.language = language
        self.on_done = on_done
        self.started = False
        _FakeDownloader.instances.append(self)

    def start(self):
        self.started = True


def _make_watcher(known_dicts=(), target_lang=None):
    _FakeDownloader.instances = []
    main_controller = _FakeMainController(target_lang)
    watcher = DictionaryDownloadWatcher(
        main_controller,
        enchant_module=_FakeEnchant(known_dicts),
        downloader_factory=_FakeDownloader,
    )
    return main_controller, watcher


def test_does_not_connect_at_all_without_enchant():
    main_controller = _FakeMainController()
    DictionaryDownloadWatcher(main_controller, enchant_module=None)
    assert main_controller.lang_controller.handlers == {}


def test_skips_download_when_dictionary_already_exists():
    main_controller, _watcher = _make_watcher(known_dicts={'de_DE'})
    main_controller.lang_controller.emit_target_lang_changed('de_DE')
    assert _FakeDownloader.instances == []


def test_skips_download_when_a_country_variant_covers_a_bare_code():
    main_controller, _watcher = _make_watcher(known_dicts={'de_DE'})
    main_controller.lang_controller.emit_target_lang_changed('de')
    assert _FakeDownloader.instances == []


def test_starts_a_download_when_nothing_covers_the_language():
    main_controller, _watcher = _make_watcher(known_dicts=set())
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    assert len(_FakeDownloader.instances) == 1
    assert _FakeDownloader.instances[0].language == 'af_ZA'
    assert _FakeDownloader.instances[0].started


def test_only_tries_each_language_once_per_run():
    main_controller, _watcher = _make_watcher(known_dicts=set())
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    assert len(_FakeDownloader.instances) == 1


def test_on_done_callback_does_not_raise():
    main_controller, _watcher = _make_watcher(known_dicts=set())
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    _FakeDownloader.instances[0].on_done()  # must not raise


def test_checks_the_already_current_language_at_construction():
    # target-lang-changed never fires for a language that's already
    # the saved default when LanguageController starts up - the
    # already-current value needs checking directly too.
    _watcher = _make_watcher(known_dicts=set(), target_lang='ca')[1]
    assert len(_FakeDownloader.instances) == 1
    assert _FakeDownloader.instances[0].language == 'ca'


def test_does_not_check_a_current_language_that_already_has_a_dictionary():
    _make_watcher(known_dicts={'ca'}, target_lang='ca')
    assert _FakeDownloader.instances == []


def test_no_current_language_is_not_an_error():
    _make_watcher(known_dicts=set(), target_lang=None)  # must not raise
    assert _FakeDownloader.instances == []
