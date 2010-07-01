#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Zuza Software Foundation
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

from gobject import SIGNAL_RUN_FIRST
from translate.storage import workflow

from virtaal.common import GObjectWrapper
from virtaal.views import UnitView

from basecontroller import BaseController


class UnitController(BaseController):
    """Controller for unit-based operations."""

    __gtype_name__ = "UnitController"
    __gsignals__ = {
        'unit-done':           (SIGNAL_RUN_FIRST, None, (object, int)),
        'unit-modified':       (SIGNAL_RUN_FIRST, None, (object,)),
        'unit-delete-text':    (SIGNAL_RUN_FIRST, None, (object, object, object, int, int, object, int)),
        'unit-insert-text':    (SIGNAL_RUN_FIRST, None, (object, object, int, object, int)),
        'unit-paste-start':    (SIGNAL_RUN_FIRST, None, (object, object, object, int)),
    }

    # INITIALIZERS #
    def __init__(self, store_controller):
        GObjectWrapper.__init__(self)

        self.current_unit = None
        self.main_controller = store_controller.main_controller
        self.main_controller.unit_controller = self
        self.store_controller = store_controller
        self.store_controller.unit_controller = self
        self.checks_controller = None
        self.placeables_controller = None
        self.workflow = None

        self.view = UnitView(self)
        self.view.connect('delete-text', self._unit_delete_text)
        self.view.connect('insert-text', self._unit_insert_text)
        self.view.connect('paste-start', self._unit_paste_start)
        self.view.connect('modified', self._unit_modified)
        self.view.connect('unit-done', self._unit_done)
        self.view.enable_signals()

        self.store_controller.connect('store-loaded', self._on_store_loaded)
        self.main_controller.connect('controller-registered', self._on_controller_registered)

        self._current_unit_modified = False
        self._recreate_workflow = False
        self._unit_state_names = {}


    # ACCESSORS #
    def get_unit_target(self, target_index):
        return self.view.get_target_n(target_index)

    def set_unit_target(self, target_index, value, cursor_pos=-1):
        self.view.set_target_n(target_index, value, cursor_pos)


    # METHODS #
    def get_unit_state_names(self, unit=None):
        if unit is None:
            unit = self.current_unit
        if not self._unit_state_names:
            from translate.storage import pocommon

            if isinstance(unit, pocommon.pounit):
                self._unit_state_names = {
                    # We don't want 'Obsolete' below, because such units are not shown anyway
                    #unit.S_OBSOLETE:     _('Obsolete'),
                    unit.S_UNTRANSLATED: _('Untranslated'),
                    unit.S_FUZZY:        _('Fuzzy'),
                    unit.S_TRANSLATED:   _('Translated'),
                }
            else:
                return {}

        return self._unit_state_names

    def load_unit(self, unit):
        if self.current_unit and self.current_unit is unit:
            return self.view
        self.current_unit = unit
        self.nplurals = self.main_controller.lang_controller.target_lang.nplurals

        if self.placeables_controller:
            unit.rich_source = self.placeables_controller.apply_parsers(unit.rich_source)

        state_n, state_id = unit.get_state_n(), unit.get_state_id()
        state_names = self.get_unit_state_names()
        if self._recreate_workflow or self.workflow is None:
            # This will only happen when a document is loaded.
            self._unit_state_names = {}
            # FIXME: The call below is run for the second time, but is necessary
            #        because the names could have changed in the new document :/
            state_names = self.get_unit_state_names()
            if state_names:
                self.workflow = workflow.create_unit_workflow(unit, state_names)
            self._recreate_workflow = False

        if state_names:
            self.workflow.reset(unit, init_state=state_names[state_id])
        # Make sure that we use the same state_n as the unit had before it got "lost"
        unit.set_state_n(state_n)
        self.view.load_unit(unit)
        return self.view

    def _unit_delete_text(self, unitview, deleted, parent, offset, cursor_pos, elem, target_num):
        self.emit('unit-delete-text', self.current_unit, deleted, parent, offset, cursor_pos, elem, target_num)

    def _unit_insert_text(self, unitview, ins_text, offset, elem, target_num):
        self.emit('unit-insert-text', self.current_unit, ins_text, offset, elem, target_num)

    def _unit_paste_start(self, unitview, old_text, offsets, target_num):
        self.emit('unit-paste-start', self.current_unit, old_text, offsets, target_num)

    def _unit_modified(self, *args):
        self.emit('unit-modified', self.current_unit)
        self._current_unit_modified = True

    def _unit_done(self, widget, unit):
        self.emit('unit-done', unit, self._current_unit_modified)
        self._current_unit_modified = False


    # EVENT HANDLERS #
    def _on_controller_registered(self, main_controller, controller):
        if controller is main_controller.lang_controller:
            self.main_controller.lang_controller.connect('source-lang-changed', self._on_language_changed)
            self.main_controller.lang_controller.connect('target-lang-changed', self._on_language_changed)
        elif controller is main_controller.checks_controller:
            self.checks_controller = controller
        elif controller is main_controller.placeables_controller:
            self.placeables_controller = controller
            self.placeables_controller.connect('parsers-changed', self._on_parsers_changed)
            self._on_parsers_changed(self.placeables_controller)

    def _on_language_changed(self, lang_controller, langcode):
        self.nplurals = lang_controller.target_lang.nplurals
        if hasattr(self, 'view'):
            self.view.update_languages()

    def _on_parsers_changed(self, placeables_controller):
        if self.current_unit:
            self.current_unit.rich_source = placeables_controller.apply_parsers(self.current_unit.rich_source)

    def _on_store_loaded(self, store_controller):
        """Call C{_on_language_changed()} and set flag to recreate workflow.

            If the target language loaded at start-up (from config) is the same
            as that of the first opened file, C{self.view.update_languages()} is
            not called, because the L{LangController}'s C{"target-lang-changed"}
            signal is never emitted, because the language has not really
            changed.

            This event handler ensures that it is loaded. As a side-effect,
            C{self.view.update_languages()} is called twice if language before
            and after a store load is different. But we'll just have to live
            with that."""
        self._on_language_changed(
            self.main_controller.lang_controller,
            self.main_controller.lang_controller.target_lang.code
        )
        self._recreate_workflow = True
