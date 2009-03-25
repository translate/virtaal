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
import re
from translate.search.match import terminologymatcher
from translate.storage.placeables.terminology import TerminologyPlaceable
from translate.storage.base import TranslationStore, TranslationUnit

from virtaal.support import opentranclient

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

        self.main_controller = controller.main_controller
        self.term_controller = controller
        self.matcher = None
        self._init_matcher()
        self.opentrantm = self._find_opentran_tm()

        if self.opentrantm is None:
            self._init_opentran_client()
        else:
            self.opentrantm.connect('match-found', self._on_match_found)

    def _find_opentran_tm(self):
        """
        Try and find an existing OpenTranClient instance, used by the OpenTran
        TM model.
        """
        plugin_ctrl = self.main_controller.plugin_controller
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

    def _init_opentran_client(self):
        """
        Create and initialize a new Open-Tran client. This should only happen
        when the Open-Tran TM model plug-in is not loaded.
        """
        plugin_ctrlr = self.main_controller.plugin_controller
        lang_ctrlr = self.main_controller.lang_controller
        # The following two values were copied from plugins/tm/__init__.py
        max_candidates = 5
        min_similarity = 70

        # Try to get max_candidates and min_quality from the TM plug-in
        if 'tm' in plugin_ctrlr.plugins:
            max_candidates = plugin_ctrlr.plugins['tm'].config['max_matches']
            min_similarity = plugin_ctrlr.plugins['tm'].config['min_quality']

        self.opentranclient = opentranclient.OpenTranClient(
            self.config['url'],
            max_candidates=max_candidates,
            min_similarity=min_similarity
        )
        self.opentranclient.source_lang = lang_ctrlr.source_lang.code
        self.opentranclient.target_lang = lang_ctrlr.target_lang.code

        self.__setup_lang_watchers()
        self.__setup_cursor_watcher()

    def __setup_cursor_watcher(self):
        unitview = self.main_controller.unit_controller.view
        def cursor_changed(cursor):
            query_str = unitview.sources[0].get_text()
            if not self.cache.has_key(query_str):
                self.cache[query_str] = None
                self.opentranclient.translate_unit(query_str, lambda *args: self.add_last_suggestions(self.opentranclient))

        store_ctrlr = self.main_controller.store_controller
        def store_loaded(store_ctrlr):
            if hasattr(self, '_cursor_connect_id'):
                self.cursor.disconnect(self._cursor_connect_id)
            self.cursor = store_ctrlr.cursor
            self._cursor_connect_id = self.cursor.connect('cursor-changed', cursor_changed)

        store_ctrlr.connect('store-loaded', store_loaded)
        if store_ctrlr.store:
            store_loaded(store_ctrlr)

    def __setup_lang_watchers(self):
        lang_controller = self.main_controller.lang_controller
        def set_source_lang(ctrlr, lang):
            if lang == self.source_lang:
                return
            self.source_lang = language
            self.cache = {}
            self.opentranclient.set_source_lang(lang)
        def set_target_lang(ctrlr, lang):
            if lang == self.target_lang:
                return
            self.target_lang = language
            self.cache = {}
            self.opentranclient.set_target_lang(language)
        self._connect_ids.append((
            lang_controller.connect('source-lang-changed', set_source_lang),
            lang_controller
        ))
        self._connect_ids.append((
            lang_controller.connect('target-lang-changed', set_target_lang),
            lang_controller
        ))


    # METHODS #
    def add_last_suggestions(self, opentranclient):
        """Grab the last suggestions from the TM client."""
        if opentranclient.last_suggestions is not None:
            added = False
            for sugg in opentranclient.last_suggestions:
                units = self.create_suggestions(sugg)
                if units:
                    for u in units:
                        self.store.addunit(u)
                    added = True
            if added:
                self.matcher.inittm(self.store)
        unitview = self.main_controller.unit_controller.view
        for src in unitview.sources:
            src.update_tree()

    def create_suggestions(self, suggestion):
        # Skip any suggestions where the suggested translation contains parenthesis
        if re.match(r'\(.*\)', suggestion['text']):
            return []

        curr_sources = [u.source for u in self.store.units]
        units = []

        for proj in suggestion['projects']:
            # Skip fuzzy matches:
            if proj['flags'] != 0:
                continue
            # Skip phrases already found:
            if proj['orig_phrase'] in curr_sources:
                continue
            # Skip any units containing parenthesis
            if re.match(r'\(.*\)', proj['orig_phrase']):
                continue
            unit = TranslationUnit(proj['orig_phrase'])
            unit.target = suggestion['text']
            units.append(unit)
        return units

    def destroy(self):
        super(TerminologyModel, self).destroy()
        if self.matcher in TerminologyPlaceable.matchers:
            TerminologyPlaceable.matchers.remove(self.matcher)


    # EVENT HANDLERS #
    def _on_match_found(self, *args):
        self.add_last_suggestions(self.opentrantm.tmclient)
