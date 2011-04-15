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

from gobject import SIGNAL_RUN_FIRST, timeout_add
from translate.storage import workflow

from virtaal.common import GObjectWrapper

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

    STATE_TIMEOUT = 200

    # INITIALIZERS #
    def __init__(self, store_controller):
        GObjectWrapper.__init__(self)

        self.current_unit = None
        self.main_controller = store_controller.main_controller
        self.main_controller.unit_controller = self
        self.store_controller = store_controller
        self.store_controller.unit_controller = self
        self.checks_controller = None

        from virtaal.views.unitview import UnitView
        self.view = UnitView(self)
        self.view.connect('delete-text', self._unit_delete_text)
        self.view.connect('insert-text', self._unit_insert_text)
        self.view.connect('paste-start', self._unit_paste_start)
        self.view.connect('modified', self._unit_modified)
        self.view.connect('unit-done', self._unit_done)
        self.view.enable_signals()

        self.store_controller.connect('store-loaded', self._on_store_loaded)
        self.main_controller.connect('controller-registered', self._on_controller_registered)

        self._recreate_workflow = False
        self._unit_state_names = {}
        self._state_timer_active = False


    # ACCESSORS #
    def get_unit_target(self, target_index):
        return self.view.get_target_n(target_index)

    def set_unit_target(self, target_index, value, cursor_pos=-1):
        self.view.set_target_n(target_index, value, cursor_pos)


    # METHODS #
    def get_unit_state_names(self, unit=None):
        self._unit_state_names = {
            #FIXME: choose friendly names
            workflow.StateEnum.EMPTY: _('Untranslated'),
            workflow.StateEnum.NEEDS_WORK: _('Needs work'),
            workflow.StateEnum.REJECTED: _('Rejected'),
            workflow.StateEnum.NEEDS_REVIEW: _('Needs Review'),
            workflow.StateEnum.UNREVIEWED: _('Translated'),
            workflow.StateEnum.FINAL: _('Reviewed'),
            }
        return self._unit_state_names

    def set_current_state(self, newstate, from_user=False):
        if isinstance(newstate, workflow.UnitState):
            newstate = newstate.state_value
        self.current_unit._current_state = newstate
        if from_user:
            # No need to update the GUI, and we should make the choice sticky
            self.current_unit._state_sticky = True
        else:
            self.view.update_state(self._unit_state_names[newstate])

    def load_unit(self, unit):
        if self.current_unit and self.current_unit is unit:
            return self.view
        self.current_unit = unit
        self.nplurals = self.main_controller.lang_controller.target_lang.nplurals

        unit._modified = False
        if not unit.STATE:
            # If the unit doesn't support states, just skip the state code
            self.view.load_unit(unit)
            return self.view

        # This unit does support states
        state_n, state_id = unit.get_state_n(), unit.get_state_id()
        state_names = self.get_unit_state_names()
        unit._state_sticky = False
        unit._current_state = state_n
        if self._recreate_workflow or True:
            # This will only happen when a document is loaded.
            self._unit_state_names = {}
            # FIXME: The call below is run for the second time, but is necessary
            #        because the names could have changed in the new document :/
            state_names = self.get_unit_state_names()
            if state_names:
                unit._workflow = workflow.create_unit_workflow(unit, state_names)
            self._recreate_workflow = False

        if state_names:
            unit._workflow.reset(unit, init_state=state_names[state_id])
            #XXX: we should make 100% sure that .reset() doesn't actually call
            # a set method in the unit, since it might cause a diff or loss of
            # meta-data.
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
        self.current_unit._modified = True
        if self.current_unit.STATE and not self.current_unit._state_sticky:
            self._start_state_timer()

    def _unit_done(self, widget, unit):
        if unit._modified and unit.STATE:
            if len(unit.target) != 0 and unit._current_state == workflow.StateEnum.EMPTY and not unit._state_sticky:
                # Oops! The user entered a translation, but the timer didn't
                # expire yet, so let's mark it fuzzy to be safe. We don't know
                # exactly what kind of fuzzy the format supports, so let's use
                # .set_state_n() directly. Also, if the workflow does more, we
                # probably don't want it, since we really only want to set the
                # state.
                unit.set_state_n(workflow.StateEnum.NEEDS_REVIEW)
            else:
                # Now really advance the workflow that we ended at
                unit._workflow.set_current_state(self._unit_state_names[unit._current_state])

        self.emit('unit-done', unit, unit._modified)
        # let's just clean up a bit:
        del unit._modified
        if unit.STATE:
            del unit._state_sticky
            del unit._current_state

    def _state_timer_expired(self, unit):
        self._state_timer_active = False
        if unit is not self.current_unit:
            return
        if unit.hasplural():
            target_len = min([len(s) for s in unit.target.strings])
        else:
            target_len = len(unit.target)
        empty_state = unit._current_state == workflow.StateEnum.EMPTY
        if target_len and empty_state:
            self.set_current_state(workflow.StateEnum.UNREVIEWED)
        elif not target_len and not empty_state:
            self.set_current_state(workflow.StateEnum.EMPTY)

    def _start_state_timer(self):
        if self._state_timer_active:
            return
        self._state_timer_active = True
        timeout_add(self.STATE_TIMEOUT, self._state_timer_expired, self.current_unit)

    def prepare_for_save(self):
        """Finalise outstanding changes to the toolkit store for saving."""
        unit = self.current_unit
        if unit._modified and unit.STATE:
            unit._workflow.set_current_state(self._unit_state_names[unit._current_state])

    # EVENT HANDLERS #
    def _on_controller_registered(self, main_controller, controller):
        if controller is main_controller.lang_controller:
            self.main_controller.lang_controller.connect('source-lang-changed', self._on_language_changed)
            self.main_controller.lang_controller.connect('target-lang-changed', self._on_language_changed)
        elif controller is main_controller.checks_controller:
            self.checks_controller = controller
        elif controller is main_controller.placeables_controller:
            controller.connect('parsers-changed', self._on_parsers_changed)
            self._on_parsers_changed(controller)

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
