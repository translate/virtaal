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
import gtk
import logging
from gtk import gdk

from virtaal.common import GObjectWrapper
from virtaal.models import UndoModel

from basecontroller import BaseController


class UndoController(BaseController):
    """Contains "undo" logic."""

    __gtype_name__ = 'UndoController'


    # INITIALIZERS #
    def __init__(self, main_controller):
        """Constructor.
            @type main_controller: virtaal.controllers.MainController"""
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.undo_controller = self
        self.unit_controller = self.main_controller.store_controller.unit_controller

        self.enabled = True
        self.model = UndoModel(self)
        self._paste_undo_info = None

        self._setup_key_bindings()
        self._connect_undo_signals()

    def _connect_undo_signals(self):
        # First connect to the unit controller
        self.unit_controller.connect('unit-delete-text', self._on_unit_delete_text)
        self.unit_controller.connect('unit-insert-text', self._on_unit_insert_text)
        self.unit_controller.connect('unit-paste-start', self._on_unit_paste_start)
        self.main_controller.store_controller.connect('store-loaded', self._on_store_loaded)

        mainview = self.main_controller.view
        mainview.gui.get_widget('menu_edit').set_accel_group(self.accel_group)
        mainview.gui.get_widget('mnu_undo').set_accel_path('<Virtaal>/Edit/Undo')
        mainview.gui.get_widget('mnu_undo').connect('activate', self._on_undo_activated)

    def _setup_key_bindings(self):
        """Setup Gtk+ key bindings (accelerators).
            This method *may* need to be moved into a view object, but if it is,
            it will be the only functionality in such a class. Therefore, it
            is done here. At least for now."""
        gtk.accel_map_add_entry("<Virtaal>/Edit/Undo", gtk.keysyms.z, gdk.CONTROL_MASK)

        self.accel_group = gtk.AccelGroup()
        # The following line was commented out, because it caused a double undo when pressing
        # Ctrl+Z, but only one if done through the menu item. This way it all works as expected.
        #self.accel_group.connect_by_path("<Virtaal>/Edit/Undo", self._on_undo_activated)

        mainview = self.main_controller.view # FIXME: Is this acceptable?
        mainview.add_accel_group(self.accel_group)


    # DECORATORS #
    def if_enabled(method):
        def enabled_method(self, *args, **kwargs):
            if self.enabled:
                return method(self, *args, **kwargs)
        return enabled_method


    # METHODS #
    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def remove_blank_undo(self):
        """Removes items from the top of the undo stack with no C{value} or
            C{action} values. The "top of the stack" is one of the top 2 items.

            This is a convenience method that can be used by any code that
            directly sets unit values."""
        if not self.model.undo_stack:
            return

        head = self.model.head()
        if not head['value'] and ('action' in head and not head['action'] or True):
            self.model.pop(permanent=True)
            return

        item = self.model.peek(offset=-1)
        if not item['value'] and ('action' in item and not item['action'] or True):
            self.model.index -= 1
            self.model.undo_stack.remove(item)

    def record_stop(self):
        self.model.recording = False

    def record_start(self):
        self.model.recording = True

    def _disable_unit_signals(self):
        """Disable all signals emitted by the unit view.
            This should always be followed, as soon as possible, by
            C{self._enable_unit_signals()}."""
        self.unit_controller.view.disable_signals()

    def _enable_unit_signals(self):
        """Enable all signals emitted by the unit view.
            This should always follow, as soon as possible, after a call to
            C{self._disable_unit_signals()}."""
        self.unit_controller.view.enable_signals()

    def _perform_undo(self, undo_info):
        self._select_unit(undo_info['unit'])
        self._disable_unit_signals()
        self.unit_controller.set_unit_target(undo_info['targetn'], undo_info['value'], undo_info['cursorpos'], escape=False)
        if 'action' in undo_info and callable(undo_info['action']):
            undo_info['action'](undo_info['unit'])
        self._enable_unit_signals()

    def _select_unit(self, unit):
        """Select the given unit in the store view.
            This is to select the unit where the undo-action took place.
            @type  unit: translate.storage.base.TranslationUnit
            @param unit: The unit to select in the store view."""
        self.main_controller.select_unit(unit, force=True)


    # EVENT HANDLERS #
    def _on_store_loaded(self, storecontroller):
        self.model.clear()

    @if_enabled
    def _on_undo_activated(self, *args):
        undo_info = self.model.pop()
        if not undo_info:
            return

        if isinstance(undo_info, list):
            for ui in reversed(undo_info):
                self._perform_undo(ui)
        else:
            self._perform_undo(undo_info)

    @if_enabled
    def _on_unit_delete_text(self, _unit_controller, unit, old_text, start_offset, end_offset, cursor_pos, target_num):
        if self._paste_undo_info:
            self.model.push(self._paste_undo_info)
            self._paste_undo_info = None
            return

        #logging.debug('_on_unit_delete_text(old_text="%s", offsets=(%d, %d), target_n=%d)' % (old_text, start_offset, end_offset, target_num))

        self.model.push({
            'unit': unit,
            'targetn': target_num,
            'value': old_text,
            'cursorpos': cursor_pos
        })

    @if_enabled
    def _on_unit_insert_text(self, _unit_controller, unit, old_text, ins_text, offset, target_num):
        if self._paste_undo_info:
            return

        #logging.debug('_on_unit_insert_text(old_text="%s", ins_text="%s", offset=%d, target_n=%d)' % (old_text, ins_text, offset, target_num))

        self.model.push({
            'unit': unit,
            'targetn': target_num,
            'value': old_text,
            'cursorpos': offset
        })

    @if_enabled
    def _on_unit_paste_start(self, _unit_controller, unit, old_text, offsets, target_num):
        if offsets['insert_offset'] == offsets['selection_offset']:
            # If there is no selection, a paste is equivalent to an insert action
            return

        self._paste_undo_info = {
            'unit': unit,
            'targetn': target_num,
            'value': old_text,
            'cursorpos': offsets['insert_offset']
        }
