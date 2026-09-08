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

"""Downloads a missing spell-check dictionary in the background the
first time a target language is selected that enchant has no
dictionary for.

Wired directly to LanguageController's own target-lang-changed signal,
independent of spellchecker.py's Plugin (which refuses to load in any
frozen build - exactly where this matters most, since there's no
system package manager to fall back on) and of ChecksController.
"""

import logging

from virtaal.support.dictionary_downloader import DictionaryDownloader

_UNSET = object()


class DictionaryDownloadWatcher:
    """No-ops entirely if enchant isn't importable - same graceful
    degradation as everywhere else spell checking touches this."""

    def __init__(self, main_controller, enchant_module=_UNSET, downloader_factory=None):
        if enchant_module is _UNSET:
            try:
                import enchant as enchant_module
            except ImportError:
                enchant_module = None
        self._enchant = enchant_module
        self._downloader_factory = downloader_factory or DictionaryDownloader
        self._tried = set()
        if self._enchant is not None:
            main_controller.lang_controller.connect(
                'target-lang-changed', self._on_target_lang_changed)

    def _has_dictionary(self, language):
        if self._enchant.dict_exists(language):
            return True
        # A bare language code ("de") counts as covered if a country
        # variant ("de_DE") is already installed - same match
        # spellchecker.py's own Plugin already does.
        return any(code == language or code.startswith(language + '_')
                   for code in self._enchant.list_languages())

    def _on_target_lang_changed(self, _lang_controller, language):
        if language in self._tried:
            return
        self._tried.add(language)
        if self._has_dictionary(language):
            return
        self._downloader_factory(
            language, on_done=lambda: self._on_done(language)).start()

    def _on_done(self, language):
        logging.debug('Dictionary download attempt finished for %s', language)
