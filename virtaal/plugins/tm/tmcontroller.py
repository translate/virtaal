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
import os.path

from virtaal.common import GObjectWrapper
from virtaal.controllers import BaseController, PluginController
from virtaal.plugins.tm import models

from tmview import TMView


class TMController(BaseController):
    """The logic-filled glue between the TM view and -model."""

    __gtype_name__ = 'TMController'
    __gsignals__ = {
        'start-query': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_STRING,))
    }

    QUERY_DELAY = 300
    """The delay after a unit is selected (C{Cursor}'s "cursor-changed" event)
        before the TM is queried."""

    # INITIALIZERS #
    def __init__(self, main_controller, max_matches):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.view = TMView(self, max_matches)
        self._load_models()

        self._connect_plugin()

    def _connect_plugin(self):
        self._store_loaded_id = self.main_controller.store_controller.connect('store-loaded', self._on_store_loaded)

        modecontroller = getattr(self.main_controller, 'mode_controller', None)
        if modecontroller is not None:
            self._mode_selected_id = modecontroller.connect('mode-selected', self._on_mode_selected)

    def _load_models(self):
        self.plugin_controller = PluginController(self)
        self.plugin_controller.PLUGIN_CLASSNAME = 'TMModel'
        self.plugin_controller.PLUGIN_DIRS = [os.path.dirname(models.__file__)]
        self.plugin_controller.PLUGIN_INTERFACE = None
        self.plugin_controller.PLUGIN_MODULE = 'virtaal.plugins.tm.models'
        self.plugin_controller.PLUGIN_NAME_ATTRIB = '__gtype_name__'
        self.plugin_controller.load_plugins()

        self._model_signal_ids = {}
        for model_name in self.plugin_controller.plugins:
            self._model_signal_ids[model_name] = self.plugin_controller.plugins[model_name].connect('match-found', self.accept_response)


    # METHODS #
    def accept_response(self, tmmodel, query_str, matches):
        """Accept a query-response from the model.
            (This method is used as Model-Controller communications)"""
        if query_str == self.current_query:
            # Perform some sanity checks on matches first
            for match in matches:
                if 'quality' not in match or match['quality'] is None:
                    match['quality'] = 0
                elif not isinstance(match['quality'], int):
                    match['quality'] = int(match['quality'])
            self.view.display_matches(matches)

    def destroy(self):
        self.main_controller.store_controller.disconnect(self._store_loaded_id)
        if getattr(self, '_cursor_changed_id', None):
            self.main_controller.store_controller.cursor.disconnect(self._cursor_changed_id)
        if getattr(self, '_mode_selected_id', None):
            self.main_controller.mode_controller.disconnect(self._mode_selected_id)
        if getattr(self, '_target_focused_id', None):
            self.main_controller.unit_controller.view.disconnect(self._target_focused_id)

        for model_name in self._model_signal_ids:
            self.plugin_controller.plugins[model_name].disconnect(self._model_signal_ids[model_name])

        self.plugin_controller.shutdown()

    def select_match(self, match_data):
        """Handle a match-selection event.
            (This method is used as View-Controller communications)"""
        unit_controller = self.main_controller.unit_controller
        target_n = unit_controller.view.focused_target_n
        old_text = unit_controller.view.get_target_n(target_n)
        unit_controller.set_unit_target(target_n, match_data['target'])
        if len(old_text) > 0:
            self.main_controller.undo_controller.remove_blank_undo()

    def send_tm_query(self, unit=None):
        """Send a new query to the TM engine.
            (This method is used as Controller-Model communications)"""
        if unit is not None:
            self.unit = unit

        self.current_query = unicode(self.unit.source)
        self.view.clear()
        self.emit('start-query', self.current_query)


    # EVENT HANDLERS #
    def _on_cursor_changed(self, cursor):
        """Start a TM query after C{self.QUERY_DELAY} milliseconds."""
        if getattr(self, '_target_focused_id', None) and getattr(self, 'unit_view', None):
            self.unit_view.disconnect(self._target_focused_id)
        self.unit_view = self.main_controller.unit_controller.view
        self._target_focused_id = self.unit_view.connect('target-focused', self._on_target_focused)
        self.unit = cursor.model[cursor.index]
        self.view.hide()

        def start_query():
            self.send_tm_query()
            return False
        if getattr(self, '_delay_id', 0):
            gobject.source_remove(self._delay_id)
        self._delay_id = gobject.timeout_add(self.QUERY_DELAY, start_query)

    def _on_mode_selected(self, modecontroller, mode):
        self.view.update_geometry()

    def _on_store_loaded(self, storecontroller):
        """Disconnect from the previous store's cursor and connect to the new one."""
        if getattr(self, '_cursor_changed_id', None):
            self.storecursor.disconnect(self._cursor_changed_id)
        self.storecursor = storecontroller.cursor
        self._cursor_changed_id = self.storecursor.connect('cursor-changed', self._on_cursor_changed)

        def handle_first_unit():
            self._on_cursor_changed(self.storecursor)
            return False
        gobject.idle_add(handle_first_unit)

    def _on_target_focused(self, unitcontroller, target_n):
        self.view.update_geometry()
