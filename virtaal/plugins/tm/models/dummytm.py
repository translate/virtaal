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

from virtaal.plugins.tm.basetmmodel import BaseTMModel

class TMModel(BaseTMModel):
    """This is a dummy (testing) translation memory model."""

    __gtype_name__ = 'DummyTMModel'

    # INITIALIZERS #
    def __init__(self, controller):
        super(TMModel, self).__init__(controller)


    # METHODS #
    def query(self, tmcontroller, query_str):
        tm_matches = []
        tm_matches.append({
            'source': 'This match has no "quality" field',
            'target': 'Hierdie woordeboek het geen "quality"-veld nie.'
        })
        tm_matches.append({
            'source': query_str.lower(),
            'target': query_str.upper(),
            'quality': 100
        })
        reverse_str = list(query_str)
        reverse_str.reverse()
        reverse_str = ''.join(reverse_str)
        tm_matches.append({
            'source': reverse_str.lower(),
            'target': reverse_str.upper(),
            'quality': 32
        })

        self.emit('match-found', query_str, tm_matches)
