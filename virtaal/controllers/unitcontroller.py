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

from gobject import GObject, SIGNAL_RUN_FIRST, TYPE_INT, TYPE_NONE, TYPE_PYOBJECT, TYPE_STRING

from virtaal.common import GObjectWrapper
from virtaal.views import UnitView

from basecontroller import BaseController


class UnitController(BaseController):
    """Controller for unit-based operations."""

    __gtype_name__ = "UnitController"
    __gsignals__ = {
        'unit-editor-created': (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_PYOBJECT,)),
        'unit-modified':       (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_PYOBJECT,)),
        'unit-delete-text':    (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_PYOBJECT, TYPE_STRING, TYPE_INT, TYPE_INT, TYPE_INT, TYPE_INT)),
        'unit-insert-text':    (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_PYOBJECT, TYPE_STRING, TYPE_STRING, TYPE_INT, TYPE_INT)),
    }

    # INITIALIZERS #
    def __init__(self, store_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = store_controller.main_controller
        self.main_controller.unit_controller = self
        self.store_controller = store_controller
        self.store_controller.unit_controller = self

        self.unit_views = {}


    # ACCESSORS #
    def get_target_language(self):
        """Get the target language via C{self.store_controller}."""
        return self.store_controller.get_target_language()

    def get_unit_target(self, target_index):
        return self.view.get_target_n(target_index)

    def set_unit_target(self, target_index, value, cursor_pos=-1):
        self.view.set_target_n(target_index, value, cursor_pos)


    # METHODS #
    def load_unit(self, unit):
        self.current_unit = unit
        self.nplurals = self.store_controller.get_nplurals()
        self.targetlang = self.store_controller.get_target_language()

        if unit in self.unit_views:
            self.view = self.unit_views[unit]
            return self.unit_views[unit]

        self._create_unitview(unit)
        self.emit('unit-editor-created', self.view)
        return self.view

    def _create_unitview(self, unit):
        self.unit_views[unit] = self.view = UnitView(self, unit)
        self.view.connect('delete-text', self._unit_delete_text)
        self.view.connect('insert-text', self._unit_insert_text)
        self.view.connect('modified', self._unit_modified)
        self.view.enable_signals()

    def _unit_delete_text(self, unitview, old_text, start_offset, end_offset, cursor_pos, target_num):
        self.emit('unit-delete-text', self.current_unit, old_text, start_offset, end_offset, cursor_pos, target_num)

    def _unit_insert_text(self, unitview, old_text, ins_text, offset, target_num):
        self.emit('unit-insert-text', self.current_unit, old_text, ins_text, offset, target_num)

    def _unit_modified(self, *args):
        self.emit('unit-modified', self.current_unit)
