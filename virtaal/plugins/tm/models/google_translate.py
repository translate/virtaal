#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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

from basetmmodel import BaseTMModel


class TMModel(BaseTMModel):
    """This is a Google Translate translation memory model.

    The plugin uses the xgoogle library (by Peteris Krumins) to query Google
    for a translation. The library can be downloaded from
    http://www.catonmat.net/blog/python-library-for-google-search/.
    """

    __gtype_name__ = 'GoogleTranslateTMModel'
    display_name = _('Machine Translation with Google Translate')
    description = _("Unreviewed machine translations from Google's translation service")

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        super(TMModel, self).__init__(controller)

        self._init_plugin()

    def _init_plugin(self):
        try:
            from xgoogle.translate import Translator, TranslationError, _languages
            self.TranslationError = TranslationError
            self.supported_langs = _languages
        except ImportError, ie:
            raise Exception('Could not import xgoogle.translate.Translator: %s' % (ie))

        self.translate = Translator().translate

        self.langcontroller = self.controller.main_controller.lang_controller
        self.srclang = self.langcontroller.source_lang.code
        self.tgtlang = self.langcontroller.target_lang.code

        self._connect_ids.append((
            self.langcontroller.connect('source-lang-changed', self._on_lang_changed, 'srclang'),
            self.langcontroller
        ))
        self._connect_ids.append((
            self.langcontroller.connect('target-lang-changed', self._on_lang_changed, 'tgtlang'),
            self.langcontroller
        ))


    # METHODS #
    def query(self, tmcontroller, query_str):
        if self.srclang not in self.supported_langs or self.tgtlang not in self.supported_langs:
            return

        try:
            tm_match = []
            tm_match.append({
                'source': query_str,
                'target': self.translate(query_str, lang_from=self.srclang, lang_to=self.tgtlang),
                'tmsource': _('Google')
            })
            self.emit('match-found', query_str, tm_match)
        except self.TranslationError, te:
            logging.exception("Google Translation error!")


    # SIGNAL HANDLERS #
    def _on_lang_changed(self, controller, lang_code, langattr):
        setattr(self, langattr, lang_code)
