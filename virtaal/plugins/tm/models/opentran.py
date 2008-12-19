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

from translate.services import opentranclient

from virtaal.plugins.tm.basetmmodel import BaseTMModel
from virtaal.common import pan_app


class TMModel(BaseTMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'OpenTranTMModel'

    default_config = {
        "url" : "http://open-tran.eu/RPC2"
    }

    # INITIALIZERS #
    def __init__(self, controller):
        super(TMModel, self).__init__(controller)
        self.load_config()

        self.tmclient = opentranclient.OpenTranClient(
            self.config["url"],
            pan_app.settings.language["contentlang"],
            max_candidates=self.config["max_candidates"],
            min_similarity=self.config["min_similarity"])



    # METHODS #
    def query(self, tmcontroller, query_str):
        if self.cache.has_key(query_str):
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            self.tmclient.translate_unit(query_str, self.handle_matches)

    def handle_matches(self, widget, query_str, matches):
        self.cache[query_str] = matches
        self.emit('match-found', query_str, matches)
