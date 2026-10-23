#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Undo and redo through a real UndoController, text box and store."""

import pytest
from gi.repository import GLib

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.test.test_scaffolding import TestScaffolding


class TestUndoAcrossUnits(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)

    @pytest.fixture(autouse=True)
    def _store(self, monkeypatch):
        # Pumping the real main loop hangs in this suite - run idle
        # callbacks here instead.
        self.idle_calls = []
        monkeypatch.setattr(GLib, 'idle_add', lambda func, *args, **kwargs: self.idle_calls.append(lambda: func(*args)))
        self.store_controller.open_file(self.testfile[1])
        self.units = self.store_controller.get_store().get_units()
        # The store view's cell editor loads the unit the cursor moves to;
        # it's never realized here.
        cursor = self.store_controller.cursor
        handler = cursor.connect('cursor-changed', lambda cursor: self._load(cursor.deref()))
        self._load(cursor.deref())
        self.undo_controller.model.clear()
        yield
        cursor.disconnect(handler)

    def _load(self, unit):
        view = self.unit_controller.load_unit(unit)
        view._layout_update_targets()

    def _run_idle(self):
        while self.idle_calls:
            self.idle_calls.pop(0)()

    def _select(self, unit):
        self.store_controller.select_unit(unit, force=True)
        self._run_idle()

    def _target(self):
        return self.unit_controller.view.targets[0]

    def _type(self, text):
        buffer = self._target().buffer
        buffer.place_cursor(buffer.get_end_iter())
        for char in text:
            buffer.begin_user_action()
            buffer.insert_interactive_at_cursor(char, -1, True)
            buffer.end_user_action()
            self._run_idle()

    def test_undo_with_nothing_to_undo_changes_nothing(self):
        self._select(self.units[0])
        before = self._target().get_text()

        self.undo_controller._on_undo_activated()

        assert self._target().get_text() == before
        assert self.undo_controller.model.peek() is None

    def test_redo_goes_back_to_the_unit_it_was_made_in_first(self):
        first, second = self.units[0], self.units[1]
        self._select(first)
        before = self._target().get_text()
        self._type('X')
        self.undo_controller._on_undo_activated()
        self._run_idle()
        assert self._target().get_text() == before
        self._select(second)

        self.undo_controller._on_redo_activated()
        self._run_idle()

        # The first redo only shows the unit, with the change still undone.
        assert self.unit_controller.current_unit is first
        assert self._target().get_text() == before
        assert self.undo_controller.model.peek_redo() is not None

        self.undo_controller._on_redo_activated()
        self._run_idle()

        assert self._target().get_text() == before + 'X'
        assert self.undo_controller.model.peek_redo() is None
