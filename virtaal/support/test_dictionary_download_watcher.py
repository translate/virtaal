#!/usr/bin/env python
#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

from virtaal.support.dictionary_download_watcher import DictionaryDownloadWatcher


class _FakeLangController:
    def __init__(self):
        self.handlers = {}

    def connect(self, signal, handler):
        self.handlers[signal] = handler

    def emit_target_lang_changed(self, language):
        self.handlers['target-lang-changed'](self, language)


class _FakeMainController:
    def __init__(self):
        self.lang_controller = _FakeLangController()


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


def _make_watcher(known_dicts=()):
    _FakeDownloader.instances = []
    main_controller = _FakeMainController()
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
