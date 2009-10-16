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
    """This is the Moses translation memory model.

    The plugin uses the Moses Statistical Machine Translation software's server to
    query over RPC for MT suggestions."""

    __gtype_name__ = 'MosesTMModel'
    display_name = _('Moses Machine Translation')
    description = _('Unreviewed machine translations from a Moses server')

    default_config = { "fr->en": "http://localhost:8080", }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        super(TMModel, self).__init__(controller)

        self.load_config()
        self.proxy = {}
        self.srclang = self.tgtlang = ''

        self._init_plugin()

    def _init_plugin(self):
        try:
            import xmlrpclib
        except ImportError, ie:
            raise Exception('Could not import xmlrpclib: %s' % (ie))

        for url_pair, server in self.config.iteritems():
            pair = url_pair.split("->")
            if self.proxy.get(pair[0]) is None:
                self.proxy[pair[0]] = {}
            self.proxy[pair[0]].update({pair[1]: xmlrpclib.ServerProxy(server)})

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
    def set_source_lang(self, language):
        self.srclang = language

    def set_target_lang(self, language):
        self._wanted_tgtlang = language

    def query(self, tmcontroller, query_str):
        if self.proxy.get(self.srclang, None) is not None:
            if self.proxy[self.srclang].get(self._wanted_tgtlang, None) is not None:
                try:
                    tm_match = []
                    tm_match.append({
                        'source': query_str,
                        'target': self.proxy[self.srclang][self._wanted_tgtlang].translate({'text': query_str})['text'],
                        #l10n: Try to keep this as short as possible. Feel free to transliterate in CJK languages for vertical display optimization.
                        'tmsource': _('Moses'),
                    })
                    self.emit('match-found', query_str, tm_match)
                except Exception, exc:
                    logging.debug('Moses TM query failed: %s' % (str(exc)))


    # SIGNAL HANDLERS #
    def _on_lang_changed(self, controller, lang_code, langattr):
        setattr(self, langattr, lang_code)
