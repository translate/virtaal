#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
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

import gobject
import logging
from translate.lang.data import languages

from virtaal.common import GObjectWrapper
from virtaal.views import LanguageView

from basecontroller import BaseController


class LanguageController(BaseController):
    """
    The logic behind language management in Virtaal.
    """

    __gtype_name__ = 'LanguageController'
    __gsignals__ = {
        'source-lang-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
        'target-lang-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
    }

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.languages = languages.copy()
        self.main_controller = main_controller
        self.main_controller.lang_controller = self
        self._source_lang = 'und'
        self._target_lang = 'und'

        self.main_controller.store_controller.connect('store-loaded', self._on_store_loaded)

        self.view = LanguageView(self)
        self.view.show()


    # ACCESSORS #
    def _get_source_lang(self):
        return self._source_lang
    def _set_source_lang(self, langcode):
        if langcode == self._source_lang:
            return
        self._source_lang = langcode
        self.emit('source-lang-changed', self._source_lang)
    source_lang = property(_get_source_lang, _set_source_lang)

    def _get_target_lang(self):
        return self._target_lang
    def _set_target_lang(self, langcode):
        if langcode == self._target_lang:
            return
        self._target_lang = langcode
        self.emit('target-lang-changed', self._target_lang)
    target_lang = property(_get_target_lang, _set_target_lang)

    # METHODS #
    def lookup_lang(self, langcode):
        """Lookup the language information of the language with the given
            language code.

            @type  langcode: str
            @param langcode: The language code (in any recognized format)
                of the language to get information for.
            @returns: An information C{dict} containing information about the
            language with the given language code (C{langcode}). If the
            language could not be found, an empty dictionary is returned.

            The returned dictionary has the following keys:
            - "name": The displayable name of the language with the given code.
            - "code": ISO 639 code with optional country code.
            - "nplurals": The number of plural forms in the language.
            - "plural": The plural expression."""
        try:
            #TODO: langcode = getstandardcode(langcode)
            langtuple = self.languages[langcode] # TODO: Should use simplercode() from the toolkit
            return {
                'name': langtuple[0],
                'code': langcode,
                'nplurals': langtuple[1],
                'plural': langtuple[2]
            }
        except KeyError:
            logging.exception('Could not find language with code %s' % (langcode))
        except Exception:
            logging.exception('LanguageController.lookup_lang("%s")' % (langcode))
        return {}


    # EVENT HANDLERS #
    def _on_store_loaded(self, store_controller):
        srclang = store_controller.store.get_source_language()
        tgtlang = store_controller.store.get_target_language()
        self.view.set_language_pair(srclang, tgtlang)

    def _on_sourcelang_changed(self, _sender, langcode):
        self.emit('source-lang-changed', langcode)

    def _on_targetlang_changed(self, _sender, langcode):
        self.emit('target-lang-changed', langcode)
