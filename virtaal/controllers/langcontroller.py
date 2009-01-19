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

from virtaal.common import GObjectWrapper
from virtaal.models import LanguageModel
from virtaal.views import LanguageView

from basecontroller import BaseController


class LanguageController(BaseController):
    """
    The logic behind language management in Virtaal.
    """

    __gtype_name__ = 'LanguageController'
    __gsignals__ = {
        'source-lang-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        'target-lang-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
    }

    NUM_RECENT = 5
    """The number of recent language pairs to save/display."""

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.lang_controller = self
        self.recent_pairs = self._load_recent()
        self._source_lang = None
        self._target_lang = None

        self.main_controller.store_controller.connect('store-loaded', self._on_store_loaded)

        self.view = LanguageView(self)
        self.view.show()


    # ACCESSORS #
    def _get_source_lang(self):
        return self._source_lang
    def _set_source_lang(self, lang):
        if isinstance(lang, basestring):
            lang = LanguageModel(lang)
        if not lang or lang == self._source_lang:
            return
        self._source_lang = lang
        self.emit('source-lang-changed', self._source_lang.code)
    source_lang = property(_get_source_lang, _set_source_lang)

    def _get_target_lang(self):
        return self._target_lang
    def _set_target_lang(self, lang):
        if isinstance(lang, basestring):
            lang = LanguageModel(lang)
        if not lang or lang == self._target_lang:
            return
        self._target_lang = lang
        self.emit('target-lang-changed', self._target_lang.code)
    target_lang = property(_get_target_lang, _set_target_lang)

    def set_language_pair(self, srclang, tgtlang):
        if isinstance(srclang, basestring):
            srclang = LanguageModel(srclang)
        if isinstance(tgtlang, basestring):
            tgtlang = LanguageModel(tgtlang)

        pair = (srclang, tgtlang)
        if pair in self.recent_pairs:
            self.recent_pairs.remove(pair)

        self.recent_pairs.insert(0, pair)
        self.recent_pairs = self.recent_pairs[:self.NUM_RECENT]

        self.source_lang = srclang
        self.target_lang = tgtlang
        self.view.update_recent_pairs()


    # METHODS #
    def _load_recent(self):
        # TODO: Load codes below from the config file
        codes = [('ar', 'en'), ('en', 'af'), ('en', 'ar'), ('en_GB', 'af')]

        recent_pairs = []
        for srccode, tgtcode in codes:
            srclang = LanguageModel(srccode)
            tgtlang = LanguageModel(tgtcode)
            recent_pairs.append((srclang, tgtlang))

        return recent_pairs

    def save_recent(self):
        pass


    # EVENT HANDLERS #
    def _on_store_loaded(self, store_controller):
        srclang = store_controller.store.get_source_language()
        tgtlang = store_controller.store.get_target_language()
        self.set_language_pair(srclang, tgtlang)
