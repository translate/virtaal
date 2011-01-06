#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2011 Zuza Software Foundation
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

from virtaal.support import tmclient

from basetmmodel import BaseTMModel


class TMModel(BaseTMModel):
    """TM back-end that allows Virtaal to connect to a remote TM server."""

    __gtype_name__ = 'RemoteTMModel'
    display_name = _('Remote Server')
    description = _('A translation memory server')
    #l10n: Try to keep this as short as possible.
    shortname = _('Remote TM')

    default_config = {
        "host" : "localhost",
        "port" : "55555",
    }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        super(TMModel, self).__init__(controller)
        self.internal_name = internal_name
        self.load_config()
        url = "http://%s:%s/tmserver" % (self.config["host"], self.config["port"])

        self.tmclient = tmclient.TMClient(url)
        self.tmclient.set_virtaal_useragent()


    # METHODS #
    def query(self, tmcontroller, unit):
        # TODO: Figure out languages
        query_str = unit.source
        if query_str in self.cache:
            _cached = self.cache[query_str]
            if _cached:
                # Only emit if we actually have something to offer
                self.emit('match-found', query_str, _cached)
        else:
            self.tmclient.translate_unit(query_str, self.source_lang, self.target_lang, self._handle_matches)

    def _handle_matches(self, widget, query_str, matches):
        """Handle the matches when returned from self.tmclient."""
        self.cache[query_str] = matches or None # None instead of empty list
        if matches:
            for match in matches:
                match['tmsource'] = self.shortname
                if not isinstance(match['target'], unicode):
                    match['target'] = unicode(match['target'], 'utf-8')
            self.emit('match-found', query_str, matches)

    def push_store(self, store_controller):
        """Add units in store to TM database on save."""
        units = []
        for unit in store_controller.store.get_units():
            if  unit.istranslated():
                units.append(unit2dict(unit))
        #FIXME: do we get source and target langs from
        #store_controller or from tm state?
        self.tmclient.add_store(store_controller.store.get_filename(), units, self.source_lang, self.target_lang)
        self.cache = {}

    def upload_store(self, store_controller):
        """Upload store to TM server."""
        self.tmclient.upload_store(store_controller.store._trans_store, self.source_lang, self.target_lang)
        self.cache = {}


def unit2dict(unit):
    return {"source": unit.source, "target": unit.target, "context": unit.getcontext()}
