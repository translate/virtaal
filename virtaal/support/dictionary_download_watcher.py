#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Downloads a missing spell-check dictionary in the background the
first time a target language is selected that enchant has no
dictionary for.

Wired directly to LanguageController's own target-lang-changed signal,
independent of spellchecker.py's Plugin (which refuses to load in any
frozen build - exactly where this matters most, since there's no
system package manager to fall back on) and of ChecksController.

Looks the language up in asset_manifest.py's cached manifest first -
no live discovery needed once it's cached, and nothing to fetch at all
if what's installed already matches the manifest's current sha, or if
the manifest (comprehensive once fetched) confirms nothing exists for
this locale. Only falls back to DictionaryDownloader's own live
discovery when the manifest itself was never fetched successfully.
"""

import logging

from virtaal.common import pan_app
from virtaal.support import asset_manifest as asset_manifest_module
from virtaal.support.asset_manifest import (
    AssetManifest,
    entry_shas,
    installed_asset_key,
)
from virtaal.support.dictionary_downloader import DictionaryDownloader

_UNSET = object()


class DictionaryDownloadWatcher:
    """No-ops entirely if enchant isn't importable - same graceful
    degradation as everywhere else spell checking touches this."""

    def __init__(self, main_controller, enchant_module=_UNSET, downloader_factory=None, asset_manifest=None,
                 schedule_after_idle_lull=None):
        if enchant_module is _UNSET:
            try:
                import enchant as enchant_module
            except ImportError:
                enchant_module = None
        self._enchant = enchant_module
        self._downloader_factory = downloader_factory or DictionaryDownloader
        self._asset_manifest = asset_manifest
        self._schedule_after_idle_lull = schedule_after_idle_lull or asset_manifest_module.schedule_after_idle_lull
        self._tried = set()
        if self._enchant is not None:
            lang_controller = main_controller.lang_controller
            lang_controller.connect('target-lang-changed', self._on_target_lang_changed)
            if lang_controller.target_lang:
                self._on_target_lang_changed(lang_controller, lang_controller.target_lang.code)

    def _has_dictionary(self, language):
        if self._enchant.dict_exists(language):
            return True
        # A bare language code ("de") counts as covered if a country
        # variant ("de_DE") is already installed - same match
        # spellchecker.py's own Plugin already does.
        return any(code == language or code.startswith(language + '_')
                   for code in self._enchant.list_languages())

    def _get_asset_manifest(self):
        if self._asset_manifest is None:
            self._asset_manifest = AssetManifest()
        return self._asset_manifest

    def _on_target_lang_changed(self, _lang_controller, language):
        if language in self._tried:
            return
        self._tried.add(language)
        if self._has_dictionary(language):
            return
        self._get_asset_manifest().ensure_fresh(
            on_done=lambda: self._maybe_download(language))

    def _maybe_download(self, language):
        manifest = self._get_asset_manifest()
        entry = manifest.get('dictionary', language)
        if entry is None:
            if not manifest.has_data():
                return self._start_live_discovery(language)
            return  # manifest is authoritative - genuinely nothing for this locale
        key = installed_asset_key('dictionary', language)
        if pan_app.settings.installed_assets.get(key) == entry_shas(entry):
            return  # already installed and unchanged
        self._schedule_after_idle_lull(lambda: self._download_known(language, entry))

    def _download_known(self, language, entry):
        downloader = self._downloader_factory(
            language, on_done=lambda success: self._on_done(language, entry, success))
        downloader.start_with_known_files(entry['folder'], [f['name'] for f in entry['files']])

    def _start_live_discovery(self, language):
        downloader = self._downloader_factory(
            language, on_done=lambda success: self._on_done(language, None, success))
        downloader.start()

    def _on_done(self, language, entry, success):
        if success and entry is not None:
            pan_app.settings.installed_assets[installed_asset_key('dictionary', language)] = entry_shas(entry)
        logging.debug('Dictionary download attempt finished for %s', language)
