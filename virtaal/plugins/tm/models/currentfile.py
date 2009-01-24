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

import re
import logging
from translate.search import match

from basetmmodel import BaseTMModel


class TMModel(BaseTMModel):
    """Translation memory model that matches against translated strings from current file"""

    __gtype_name__ = 'CurrentFileTMModel'
    display_name = _('Currently open file')

    default_config = { 'max_length': 1000 }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        super(TMModel, self).__init__(controller)

        self.matcher = None
        self.internal_name = internal_name
        self.controller.main_controller.store_controller.connect('store-loaded', self.recreate_matcher)
        self.controller.main_controller.store_controller.unit_controller.connect('unit-done', self._on_unit_modified)
        self.load_config()


    # METHODS #
    def recreate_matcher(self, storecontroller):
        store = storecontroller.get_store()._trans_store
        options = {
            'max_length': int(self.config['max_length']),
            'max_candidates': self.controller.max_matches,
            'min_similarity': self.controller.min_quality
        }
        self.matcher = match.matcher(store, **options)

    def query(self, tmcontroller, query_str):
        if self.cache.has_key(query_str):
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            matches = [match.unit2dict(candidate) for candidate in self.matcher.matches(unicode(query_str, "utf-8"))]
            self.cache[query_str] = filter(lambda m: m['quality'] != u'100', matches)
            self.emit('match-found', query_str, self.cache[query_str])

    def _on_unit_modified(self, widget, new_unit):
        """Add the new translation unit to the TM."""
        if new_unit.istranslated():
            self.matcher.extendtm(new_unit)
            self.cache = {}
