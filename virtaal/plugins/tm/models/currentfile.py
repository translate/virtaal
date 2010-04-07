#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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
    display_name = _('Current File')
    description = _('Translated units from the currently open file')

    default_config = { 'max_length': 1000 }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        super(TMModel, self).__init__(controller)

        self.matcher = None
        self.internal_name = internal_name
        self.load_config()

        self._connect_ids.append((
            self.controller.main_controller.store_controller.connect('store-loaded', self.recreate_matcher),
            self.controller.main_controller.store_controller
        ))
        if self.controller.main_controller.store_controller.get_store() is not None:
            self.recreate_matcher(self.controller.main_controller.store_controller)

        self._connect_ids.append((
            self.controller.main_controller.store_controller.unit_controller.connect('unit-done', self._on_unit_modified),
            self.controller.main_controller.store_controller.unit_controller
        ))


    # METHODS #
    def recreate_matcher(self, storecontroller):
        store = storecontroller.get_store()._trans_store
        if self.matcher is None:
            options = {
                'max_length': int(self.config['max_length']),
                'max_candidates': self.controller.max_matches,
                'min_similarity': self.controller.min_quality
            }
            self.matcher = match.matcher(store, **options)
        else:
            for unit in store.units:
                if unit.istranslatable() and unit.istranslated():
                    self.matcher.extendtm(unit)
        self.cache = {}

    def query(self, tmcontroller, unit):
        query_str = unit.source
        if self.cache.has_key(query_str):
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            self.cache[query_str] = \
                    self._check_other_units(unit) + \
                    self._check_xliff_alttrans(unit)
            self.emit('match-found', query_str, self.cache[query_str])

    def _check_other_units(self, unit):
        matches = []

        query_str = unit.source
        if not isinstance(query_str, unicode):
            query_str = unicode(query_str, 'utf-8')

        for candidate in self.matcher.matches(query_str):
            m = match.unit2dict(candidate)
            #l10n: Try to keep this as short as possible.
            m['tmsource'] = _('This file')
            matches.append(m)
        return [m for m in matches if m['quality'] != u'100']

    def _check_xliff_alttrans(self, unit):
        if not hasattr(unit, 'getalttrans'):
            return []
        alttrans = unit.getalttrans()
        if not alttrans:
            return []

        from translate.search.lshtein import LevenshteinComparer
        lcomparer = LevenshteinComparer(max_len=1000)

        results = []
        for alt in alttrans:
            tmsource = _('This file')

            origin = alt.xmlelement.get('from', '')
            if not origin:
                origin = alt.xmlelement.get('origin', '')
            if origin:
                tmsource += "\n" + origin

            results.append({
                'source': alt.source,
                'target': alt.target,
                'quality': lcomparer.similarity(unit.source, alt.source, 0),
                'tmsource': tmsource,
            })
        return results


    # EVENT HANDLERS #
    def _on_unit_modified(self, widget, new_unit, modified):
        """Add the new translation unit to the TM."""
        if modified and new_unit.istranslated():
            self.matcher.extendtm(new_unit)
            self.cache = {}
