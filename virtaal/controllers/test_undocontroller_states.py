#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Undo and redo of workflow-state changes in XLIFF and Qt Linguist
files (#3900), through a real UndoController, unit view and store.

Each format maps its own state numbers onto StateEnum differently.
XLIFF has state numbers between the StateEnum steps (state="new" is
1, needs-l10n 32, needs-review-l10n 82, final 121), and undo must
bring back that number, not just its StateEnum step."""

import os
import tempfile

import pytest
from gi.repository import GLib
from translate.storage import factory, workflow

from virtaal.controllers import unitcontroller as unitcontroller_module
from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.test.test_scaffolding import TestScaffolding

S = workflow.StateEnum

XLIFF = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
<file original="states.xlf" source-language="en" target-language="af" datatype="plaintext">
<body>
<trans-unit id="1"><source>No target</source></trans-unit>
<trans-unit id="2"><source>New</source><target state="new"></target></trans-unit>
<trans-unit id="3"><source>Needs translation</source>
  <target state="needs-translation">Moet vertaal word</target></trans-unit>
<trans-unit id="4"><source>Needs l10n</source>
  <target state="needs-l10n">Moet gelokaliseer word</target></trans-unit>
<trans-unit id="5" approved="no"><source>Needs review</source>
  <target state="needs-review-translation">Moet nagegaan word</target></trans-unit>
<trans-unit id="6" approved="no"><source>Needs l10n review</source>
  <target state="needs-review-l10n">Lokalisering moet nagegaan word</target></trans-unit>
<trans-unit id="7" approved="yes"><source>Translated</source>
  <target state="translated">Vertaal</target></trans-unit>
<trans-unit id="8" approved="yes"><source>Signed off</source>
  <target state="signed-off">Goedgekeur</target></trans-unit>
<trans-unit id="9" approved="yes"><source>Final</source>
  <target state="final">Finaal</target></trans-unit>
</body>
</file>
</xliff>
"""

# source: the unit's state number when loaded
XLIFF_STATES = {
    'No target': 0,
    'New': 1,
    'Needs translation': 30,
    'Needs l10n': 32,
    'Needs review': 80,
    'Needs l10n review': 82,
    'Translated': 100,
    'Signed off': 120,
    'Final': 121,
}

TS = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="af">
<context>
    <name>Main</name>
    <message>
        <source>Untranslated</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <source>Unfinished</source>
        <translation type="unfinished">Onvoltooid</translation>
    </message>
    <message>
        <source>Finished</source>
        <translation>Voltooi</translation>
    </message>
    <message>
        <source>Obsolete</source>
        <translation type="obsolete">Uitgedien</translation>
    </message>
    <message>
        <source>Vanished</source>
        <translation type="vanished">Verdwyn</translation>
    </message>
</context>
</TS>
"""

TS_STATES = {
    'Untranslated': 0,
    'Unfinished': 30,
    'Finished': 100,
}


class _StateUndo(TestScaffolding):
    SUFFIX = None
    CONTENT = None
    STATES = None
    TRANSLATED = None
    # source: the state a pick is saved as, where the format can't keep it
    SAVED_PICK = {}

    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)
        fd, self.statefile = tempfile.mkstemp(suffix=self.SUFFIX, prefix='test_undo_states')
        os.close(fd)

    def teardown_class(self):
        os.unlink(self.statefile)
        TestScaffolding.teardown_class(self)

    @pytest.fixture(autouse=True)
    def _store(self, monkeypatch):
        # Pumping the real main loop hangs in this suite - run idle
        # callbacks, and the state timer, here instead.
        self.idle_calls = []
        # A state timer an earlier test left pending would block this one's.
        self.unit_controller._state_timer_active = False

        def later(func, *args, **kwargs):
            self.idle_calls.append(lambda: func(*args))

        monkeypatch.setattr(GLib, 'idle_add', later)
        monkeypatch.setattr(
            unitcontroller_module, 'timeout_add', lambda ms, func, *a: later(func, *a)
        )
        with open(self.statefile, 'w', encoding='utf-8') as f:
            f.write(self.CONTENT)
        self.store_controller.open_file(self.statefile)
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

    def _unit(self, source):
        return next(u for u in self.store_controller.get_store().get_units() if u.source == source)

    def _select(self, source):
        unit = self._unit(source)
        self.store_controller.select_unit(unit, force=True)
        self._run_idle()
        assert self.unit_controller.current_unit is unit
        return unit

    def _leave(self, source):
        unit = self.unit_controller.current_unit
        other = next(s for s in self.STATES if s != source)
        self._select(other)
        # Leaving finished it: an error there is only logged.
        assert not hasattr(unit, '_current_state')

    def _statenav(self):
        return self.unit_controller.view._widgets['state']

    def _pick(self, state_id):
        """Click a state in the state list, as the dropdown does."""
        name = self.unit_controller._unit_state_names[state_id]
        statenav = self._statenav()
        row = next(row for row in statenav.tvw_items.get_model() if row[0] == name)
        assert name not in statenav.unselectable
        statenav.tvw_items.set_cursor(row.path[0])
        self._run_idle()

    def _undo(self):
        self.undo_controller._on_undo_activated()
        self._run_idle()

    def _redo(self):
        self.undo_controller._on_redo_activated()
        self._run_idle()

    def _target(self):
        return self.unit_controller.view.targets[0]

    def _type(self, text):
        buffer = self._target().buffer
        buffer.place_cursor(buffer.get_end_iter())
        buffer.begin_user_action()
        buffer.insert_interactive_at_cursor(text, -1, True)
        buffer.end_user_action()
        self._run_idle()

    def _clear_target(self):
        """Select the whole target and press Backspace, then let the
        state timer run."""
        textbox = self._target()
        buffer = textbox.buffer
        buffer.select_range(buffer.get_start_iter(), buffer.get_end_iter())
        textbox.emit('backspace')
        self._run_idle()

    def _assert_state(self, unit, state_n):
        assert unit._current_state == state_n
        # The state list shows its StateEnum step.
        state_name = self.unit_controller._unit_state_names[unit.get_state_id(state_n)]
        assert self._statenav().btn_popup.get_label() == state_name

    def _saved(self, source):
        """Save, read the file again and return its unit for source."""
        self.store_controller.save_file()
        store = factory.getobject(self.statefile)
        return next(u for u in store.units if u.source == source)

    def _picks(self, unit):
        """Every state the list lets this unit be given, other than its own."""
        own = unit.get_state_id()
        statenav = self._statenav()
        return [
            state_id
            for state_id, name in sorted(self.unit_controller._unit_state_names.items())
            if state_id in unit.STATE
            and state_id >= S.EMPTY
            and state_id != own
            and name not in statenav.unselectable
        ]

    def test_the_fixture_loads_each_state(self):
        for source, state_n in self.STATES.items():
            assert self._unit(source).get_state_n() == state_n, source

    def test_undo_and_redo_of_state_picks(self, source):
        state_n = self.STATES[source]
        unit = self._select(source)
        self.undo_controller.model.clear()
        picks = self._picks(unit)
        assert picks
        # Each pick in turn, then undo them all, then redo them all.
        for state_id in reversed(picks):
            self._pick(state_id)
            self._assert_state(unit, state_id)
        history = [state_n, *reversed(picks)]
        for i in range(len(picks), 0, -1):
            self._undo()
            self._assert_state(unit, history[i - 1])
        assert self.undo_controller.model.peek() is None
        for i in range(1, len(history)):
            self._redo()
            self._assert_state(unit, history[i])
        # And undo back to where it started.
        for _ in picks:
            self._undo()
        self._assert_state(unit, state_n)

    def test_an_undone_state_pick_is_saved_as_the_original_state(self, source):
        state_n = self.STATES[source]
        unit = self._select(source)
        self.undo_controller.model.clear()
        self._pick(self._picks(unit)[0])
        self._undo()
        self._assert_state(unit, state_n)
        self._leave(source)

        assert self._saved(source).get_state_n() == state_n

    def test_a_redone_state_pick_is_saved(self, source):
        unit = self._select(source)
        self.undo_controller.model.clear()
        picked = self._picks(unit)[-1]
        self._pick(picked)
        self._undo()
        self._redo()
        self._leave(source)

        assert self._saved(source).get_state_id() == self.SAVED_PICK.get(source, picked)

    def test_undoing_a_cleared_target_restores_its_text_and_state_together(self, translated_source):
        source = translated_source
        state_n = self.STATES[source]
        unit = self._select(source)
        text = self._target().get_text()
        self.undo_controller.model.clear()

        self._clear_target()
        assert self._target().get_text() == ''
        self._assert_state(unit, S.EMPTY)

        self._undo()
        assert self._target().get_text() == text
        self._assert_state(unit, state_n)
        # Text and state came back in the one step.
        assert self.undo_controller.model.peek() is None

        self._redo()
        assert self._target().get_text() == ''
        self._assert_state(unit, S.EMPTY)

        self._undo()
        assert self._target().get_text() == text
        self._assert_state(unit, state_n)

    def test_an_undone_cleared_target_is_saved_with_its_state(self, translated_source):
        source = translated_source
        state_n = self.STATES[source]
        unit = self._select(source)
        text = unit.target
        self.undo_controller.model.clear()
        self._clear_target()
        self._undo()
        self._leave(source)

        saved = self._saved(source)
        assert saved.target == text
        assert saved.get_state_n() == state_n

    def test_editing_the_text_keeps_the_units_state(self, translated_source):
        source = translated_source
        state_n = self.STATES[source]
        unit = self._select(source)
        self._type('!')
        self._assert_state(unit, state_n)
        self._leave(source)

        saved = self._saved(source)
        assert saved.target.endswith('!')
        assert saved.get_state_n() == state_n

    def test_a_redone_cleared_target_is_saved_untranslated(self, translated_source):
        source = translated_source
        self._select(source)
        self.undo_controller.model.clear()
        self._clear_target()
        self._undo()
        self._redo()
        self._leave(source)

        saved = self._saved(source)
        assert not saved.target
        assert saved.get_state_id() == S.EMPTY


def pytest_generate_tests(metafunc):
    cls = metafunc.cls
    if cls is None or cls.STATES is None:
        return
    if 'source' in metafunc.fixturenames:
        metafunc.parametrize('source', list(cls.STATES))
    if 'translated_source' in metafunc.fixturenames:
        metafunc.parametrize('translated_source', list(cls.TRANSLATED))


class TestXliffStateUndo(_StateUndo):
    SUFFIX = '.xlf'
    CONTENT = XLIFF
    STATES = XLIFF_STATES
    TRANSLATED = [s for s in XLIFF_STATES if XLIFF_STATES[s] >= S.NEEDS_WORK]

    def test_typing_into_a_new_unit_translates_it(self):
        unit = self._select('New')

        self._type('Nuut')

        self._assert_state(unit, S.UNREVIEWED)
        self._leave('New')
        assert self._saved('New').get_state_n() == S.UNREVIEWED

    def test_a_new_unit_left_before_the_state_timer_needs_review(self):
        self._select('New')
        self.unit_controller._state_timer_active = True  # the timer never fires

        self._type('Nuut')
        self._leave('New')

        assert self._saved('New').get_state_n() == S.NEEDS_REVIEW


class TestTsStateUndo(_StateUndo):
    SUFFIX = '.ts'
    CONTENT = TS
    STATES = TS_STATES
    TRANSLATED = ['Unfinished', 'Finished']
    # Qt has no needs-work for an empty message: unfinished is untranslated.
    SAVED_PICK = {'Untranslated': S.EMPTY}

    def test_obsolete_and_vanished_messages_are_not_editable(self):
        sources = [u.source for u in self.store_controller.get_store().get_units()]
        assert 'Obsolete' not in sources
        assert 'Vanished' not in sources
