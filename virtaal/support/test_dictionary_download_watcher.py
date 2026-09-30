#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common import pan_app
from virtaal.support import asset_manifest as am
from virtaal.support.asset_manifest import entry_shas, installed_asset_key
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
        self.known_files_call = None
        _FakeDownloader.instances.append(self)

    def start(self):
        self.started = True

    def start_with_known_files(self, folder, files):
        self.known_files_call = (folder, files)


class _FakeAssetManifest:
    """entries: {(resource_type, locale): entry}. ensure_fresh() always
    calls on_done() immediately - the manifest's own refresh timing is
    tested separately in test_asset_manifest.py."""

    def __init__(self, entries=None):
        self.entries = entries or {}

    def ensure_fresh(self, on_done=None):
        (on_done or (lambda: None))()

    def get(self, resource_type, locale_code):
        return self.entries.get((resource_type, locale_code))


def _make_watcher(known_dicts=(), target_lang=None, manifest_entries=None, lull_calls=None):
    _FakeDownloader.instances = []
    lull_calls = lull_calls if lull_calls is not None else []
    main_controller = _FakeMainController(target_lang)
    watcher = DictionaryDownloadWatcher(
        main_controller,
        enchant_module=_FakeEnchant(known_dicts),
        downloader_factory=_FakeDownloader,
        asset_manifest=_FakeAssetManifest(manifest_entries),
        schedule_after_idle_lull=lambda callback: lull_calls.append(callback),
    )
    return main_controller, watcher


def _reset_installed_assets():
    pan_app.settings.installed_assets = {}


def test_does_not_connect_at_all_without_enchant():
    main_controller = _FakeMainController()
    DictionaryDownloadWatcher(main_controller, enchant_module=None)
    assert main_controller.lang_controller.handlers == {}


def test_lazily_constructs_a_real_asset_manifest_when_none_is_injected():
    main_controller = _FakeMainController()
    watcher = DictionaryDownloadWatcher(
        main_controller,
        enchant_module=_FakeEnchant(known_dicts=set()),
        downloader_factory=_FakeDownloader,
    )
    assert watcher._asset_manifest is None
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    assert isinstance(watcher._asset_manifest, am.AssetManifest)


def test_skips_download_when_dictionary_already_exists():
    main_controller, _watcher = _make_watcher(known_dicts={'de_DE'})
    main_controller.lang_controller.emit_target_lang_changed('de_DE')
    assert _FakeDownloader.instances == []


def test_skips_download_when_a_country_variant_covers_a_bare_code():
    main_controller, _watcher = _make_watcher(known_dicts={'de_DE'})
    main_controller.lang_controller.emit_target_lang_changed('de')
    assert _FakeDownloader.instances == []


def test_falls_back_to_live_discovery_when_manifest_has_no_entry():
    main_controller, _watcher = _make_watcher(known_dicts=set())
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    assert len(_FakeDownloader.instances) == 1
    assert _FakeDownloader.instances[0].language == 'af_ZA'
    assert _FakeDownloader.instances[0].started
    assert _FakeDownloader.instances[0].known_files_call is None


def test_only_tries_each_language_once_per_run():
    main_controller, _watcher = _make_watcher(known_dicts=set())
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    assert len(_FakeDownloader.instances) == 1


def test_on_done_callback_does_not_raise():
    main_controller, _watcher = _make_watcher(known_dicts=set())
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    _FakeDownloader.instances[0].on_done(True)  # must not raise


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


_AF_ZA_ENTRY = {'folder': 'af', 'files': [
    {'name': 'af_ZA.aff', 'sha': 's1'},
    {'name': 'af_ZA.dic', 'sha': 's2'},
]}


def test_downloads_via_known_files_after_a_lull_when_manifest_has_an_entry():
    _reset_installed_assets()
    lull_calls = []
    main_controller, _watcher = _make_watcher(
        known_dicts=set(), manifest_entries={('dictionary', 'af_ZA'): _AF_ZA_ENTRY}, lull_calls=lull_calls)
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')

    assert _FakeDownloader.instances == []  # not yet - waiting for the lull
    assert len(lull_calls) == 1
    lull_calls[0]()  # simulate the lull passing

    assert len(_FakeDownloader.instances) == 1
    downloader = _FakeDownloader.instances[0]
    assert downloader.known_files_call == ('af', ['af_ZA.aff', 'af_ZA.dic'])
    assert not downloader.started


def test_skips_download_when_installed_sha_already_matches_the_manifest():
    _reset_installed_assets()
    pan_app.settings.installed_assets[installed_asset_key('dictionary', 'af_ZA')] = entry_shas(_AF_ZA_ENTRY)
    main_controller, _watcher = _make_watcher(
        known_dicts=set(), manifest_entries={('dictionary', 'af_ZA'): _AF_ZA_ENTRY})
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    assert _FakeDownloader.instances == []


def test_records_installed_sha_only_on_a_successful_known_download():
    _reset_installed_assets()
    lull_calls = []
    main_controller, _watcher = _make_watcher(
        known_dicts=set(), manifest_entries={('dictionary', 'af_ZA'): _AF_ZA_ENTRY}, lull_calls=lull_calls)
    main_controller.lang_controller.emit_target_lang_changed('af_ZA')
    lull_calls[0]()
    key = installed_asset_key('dictionary', 'af_ZA')

    _FakeDownloader.instances[0].on_done(False)
    assert key not in pan_app.settings.installed_assets

    _FakeDownloader.instances[0].on_done(True)
    assert pan_app.settings.installed_assets[key] == entry_shas(_AF_ZA_ENTRY)
