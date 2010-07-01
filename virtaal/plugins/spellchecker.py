#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Zuza Software Foundation
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

import logging
import sys
import os
import os.path
from cStringIO import StringIO
import tarfile

from virtaal.__version__ import ver as version
from virtaal.common import pan_app
from virtaal.controllers import BasePlugin
from virtaal.support.httpclient import HTTPClient

if not pan_app.DEBUG:
    try:
        import psyco
    except:
        psyco = None
else:
    psyco = None

class Plugin(BasePlugin):
    """A plugin to control spell checking.

    It can also download spell checkers on Windows."""

    display_name = _('Spell Checker')
    description = _('Check spelling and provide suggestions')
    version = 0.1

    _base_URL = 'http://dictionary.locamotion.org/hunspell/'
    _dict_URL = _base_URL + '%s.tar.bz2'
    _lang_list = 'languages.txt'

    # INITIALIZERS #
    def __init__(self, internal_name, main_controller):
        self.internal_name = internal_name

        # If these imports fail, the plugin is automatically disabled
        import gtkspell
        import enchant
        self.gtkspell = gtkspell
        self.enchant = enchant

        self.unit_view = main_controller.unit_controller.view
        self._connect_id = self.unit_view.connect('textview-language-changed', self._on_unit_lang_changed)
        self.clients = {}
        self.languages = set()

    def destroy(self):
        """Remove signal connections and disable spell checking."""
        if getattr(self, '_connect_id', None):
            self.unit_view.disconnect(self._connect_id)
        for text_view in self.unit_view.sources + self.unit_view.targets:
            self._disable_checking(text_view)

    # METHODS #
    def _download_checker(self, language):
        """A Windows-only way to obtain new dictionaries."""
        if 'APPDATA' not in os.environ:
            # We won't have an idea of where to save it, so let's give up now
            return
        if language in self.clients:
            # We already tried earlier, or started the process
            return
        if not self.languages:
            if self._lang_list not in self.clients:
                # We don't yet have a list of available languages
                url = self._base_URL + self._lang_list #index page listing all the dictionaries
                callback = lambda *args: self._process_index(language=language, *args)
                client = HTTPClient()
                client.set_virtaal_useragent()
                client.get(url, callback)
                self.clients[self._lang_list] = client
                # self._process_index will call this again, so we can exit
            return

        # Let's see if a dictionary is available for this language:
        for l in self.languages:
            if l == language or l.startswith(language+'_'):
                self.clients[language] = None
                logging.debug("Will use %s to spell check %s", l, language)
                language = l
                break
        else:
            # No dictionary available
            # Indicate that we never need to try this language:
            logging.debug("Found no suitable language for spell checking")
            self.clients[language] = None
            return

       # Now download the actual files after we have determined that it is
       # available
        self.clients[language] = HTTPClient()
        self.clients[language].set_virtaal_useragent()
        callback = lambda *args: self._process_tarball(language=language, *args)
        url = self._dict_URL % language

        if logging.root.level != logging.DEBUG:
            self.clients[language].get(url, callback)
        else:
            def error_log(request, result):
                logging.debug('Could not get %s: status %d' % (url, request.status))
            self.clients[language].get(url, callback, error_callback=error_log)

    def _tar_ok(self, tar):
        # TODO: Verify that the tarball is ok:
        # - only two files
        # - must be .aff and .dic
        # - language codes should be sane
        # - file sizes should be ok
        # - no directory structure
        return True

    def _ensure_dir(self, dir):
        if not os.path.isdir(dir):
            os.makedirs(dir)

    def _process_index(self, request, result, language=None):
        """Process the list of languages."""
        if request.status == 200 and not self.languages:
            self.languages = set(result.split())
            self._download_checker(language)
        else:
            logging.debug("Couldn't get list of spell checkers")
            #TODO: disable plugin

    def _process_tarball(self, request, result, language=None):
        # Indicate that we already tried and shouldn't try again later:
        self.clients[language] = None

        if request.status == 200:
            logging.debug('Got a dictionary')
            file_obj = StringIO(result)
            tar = tarfile.open(fileobj=file_obj)
            if not self._tar_ok(tar):
                return
            DICTDIR = os.path.join(os.environ['APPDATA'], 'enchant', 'myspell')
            self._ensure_dir(DICTDIR)
            tar.extractall(DICTDIR)
            self.unit_view.update_languages()
        else:
            logging.debug("Couldn't get a dictionary. Status code: %d" % (request.status))

    def _disable_checking(self, text_view):
        """Disable checking on the given text_view."""
        spell = None
        try:
            spell = self.gtkspell.get_from_text_view(text_view)
        except SystemError, e:
            # At least on Mandriva .get_from_text_view() sometimes returns
            # a SystemError without a description. Things seem to work fine
            # anyway, so let's ignore it and hope for the best.
            pass
        if not spell is None:
            spell.detach()
        text_view.spell_lang = None
    if psyco:
        psyco.cannotcompile(_disable_checking)


    # SIGNAL HANDLERS #
    def _on_unit_lang_changed(self, unit_view, text_view, language):
        if not self.gtkspell:
            return

        if not self.enchant.dict_exists(language):
            # Sometimes enchants *wants* a country code, other times it does not.
            # For the cases where it requires one, we look for the first language
            # code that enchant supports and use that one.
            for code in self.enchant.list_languages():
                if code.startswith(language):
                    language = code
                    break
            else:
                #logging.debug('No code in enchant.list_languages() that starts with "%s"' % (language))

                # If we are on Windows, let's try to download a spell checker:
                if os.name == 'nt':
                    self._download_checker(language)
                    # If we get it, it will only be activated asynchronously
                    # later
                #TODO: packagekit on Linux?

                # We couldn't find a dictionary for "language", so we should make sure that we don't
                # have a spell checker for a different language on the text view. See bug 717.
                self._disable_checking(text_view)
                return

        try:
            spell = None
            try:
                spell = self.gtkspell.get_from_text_view(text_view)
            except SystemError, e:
                # At least on Mandriva .get_from_text_view() sometimes returns
                # a SystemError without a description. Things seem to work fine
                # anyway, so let's ignore it and hope for the best.
                pass
            if spell is None:
                spell = self.gtkspell.Spell(text_view, language)
            else:
                spell.set_language(language)
                spell.recheck_all()
            text_view.spell_lang = language
        except Exception, e:
            logging.exception("Could not initialize spell checking", e)
            self.gtkspell = None
            #TODO: unload plugin

    if psyco:
        psyco.cannotcompile(_on_unit_lang_changed)
