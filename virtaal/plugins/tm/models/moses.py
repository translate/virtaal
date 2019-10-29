#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2011 Zuza Software Foundation
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

from six import text_type

from basetmmodel import BaseTMModel


class TMModel(BaseTMModel):
    """This is the Moses translation memory model.

    The plugin uses the Moses Statistical Machine Translation software's server to
    query over RPC for MT suggestions."""

    __gtype_name__ = 'MosesTMModel'
    display_name = _('Moses')
    description = _('Unreviewed machine translations from a Moses server')

    default_config = { "fr->en": "http://localhost:8080", }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        super(TMModel, self).__init__(controller)

        self.load_config()
        self.clients = {}
        self._init_plugin()

    def _init_plugin(self):
        from virtaal.support.mosesclient import MosesClient
        # let's map servers to clients to detect duplicates
        client_map = {}
        for lang_pair, server in self.config.iteritems():
            pair = lang_pair.split("->")
            if self.clients.get(pair[0]) is None:
                self.clients[pair[0]] = {}
            if server in client_map:
                client = client_map[server]
                client.set_multilang()
            else:
                client = MosesClient(server)
                client_map[server] = client
            self.clients[pair[0]].update({pair[1]: client})


    # METHODS #
    def query(self, tmcontroller, unit):
        if self.source_lang in self.clients and self.target_lang in self.clients[self.source_lang]:
            query_str = text_type(unit.source) # cast in case of multistrings
            if query_str in self.cache:
                self.emit('match-found', query_str, [self.cache[query_str]])
                return

            client = self.clients[self.source_lang][self.target_lang]
            client.translate_unit(query_str, self._handle_response, self.target_lang)
            return

    def _handle_response(self, id, response):
        if not response:
            return
        result = {
            'source': id,
            'target': response,
            #l10n: Try to keep this as short as possible. Feel free to transliterate in CJK languages for vertical display optimization.
            'tmsource': _('Moses'),
        }

        self.cache[id] = result
        self.emit('match-found', id, [result])
