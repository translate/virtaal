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
import os
from translate.search.match import terminologymatcher
from translate.storage.placeables.terminology import TerminologyPlaceable
from translate.storage.base import TranslationStore, TranslationUnit

from basetermmodel import BaseTerminologyModel


class TerminologyModel(BaseTerminologyModel):
    """
    Terminology model that queries Open-tran.eu for terminology results.
    """

    __gtype_name__ = 'OpenTranTerminology'
    display_name = _('Open-Tran.eu Terminology')

    default_config = { "url" : "http://open-tran.eu/RPC2" }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        super(TerminologyModel, self).__init__(controller)

        self.internal_name = internal_name
        self.load_config()

        self.term_controller = controller
        self.matcher = None
        self._init_matcher()
        self.opentrantm = self._find_opentran_tm()

        if self.opentrantm:
            self.opentrantm.connect('match-found', self._on_match_found)

    def _find_opentran_tm(self):
        """
        Try and find an existing OpenTranClient instance, used by the OpenTran
        TM model.
        """
        plugin_ctrl = self.term_controller.main_controller.plugin_controller
        if 'tm' not in plugin_ctrl.plugins:
            return None

        tm_ctrl = plugin_ctrl.plugins['tm'].tmcontroller
        if 'opentran' not in tm_ctrl.plugin_controller.plugins:
            return None

        return tm_ctrl.plugin_controller.plugins['opentran']

    def _init_matcher(self):
        """
        Initialize the matcher to be used by the C{TerminologyPlaceable} parser.
        """
        if self.matcher in TerminologyPlaceable.matchers:
            TerminologyPlaceable.matchers.remove(self.matcher)

        self.store = TranslationStore()
        self.matcher = terminologymatcher(self.store)
        TerminologyPlaceable.matchers.append(self.matcher)


    # METHODS #
    def destroy(self):
        super(TerminologyModel, self).destroy()
        if self.matcher in TerminologyPlaceable.matchers:
            TerminologyPlaceable.matchers.remove(self.matcher)


    # EVENT HANDLERS #
    def _on_match_found(self, *args):
        """
        Grab the last suggestions from the TM client.

        @param args: Arguments we don't care about.
        """
        if self.opentrantm.tmclient.last_suggestions is None:
            return

        added = False
        curr_sources = [u.source for u in self.store.units]
        for sugg in self.opentrantm.tmclient.last_suggestions:
            for proj in sugg['projects']:
                if proj['flags'] != 0:
                    # Skip fuzzy matches
                    continue
                if proj['orig_phrase'] in curr_sources:
                    # Skip phrases already found
                    continue
                unit = TranslationUnit(proj['orig_phrase'])
                unit.target = sugg['text']
                #logging.debug('Adding terminology unit: "%s" => "%s"' % (unit.source, unit.target))
                self.store.addunit(unit)
                added = True
        if added:
            self.matcher.inittm(self.store)
            unitview = self.controller.main_controller.unit_controller.view
            for src in unitview.sources:
                src.update_tree()
