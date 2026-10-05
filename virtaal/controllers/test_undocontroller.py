#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.storage.placeables import StringElem

from virtaal.controllers import undocontroller as undocontroller_module
from virtaal.controllers.undocontroller import UndoController
from virtaal.models.undomodel import UndoModel


class _FakeGuiInfo:
    """Just enough of StringElemGUI for _on_unit_insert_text's own
        undo_action() (elem.gui_info.gui_to_tree_index()) - a flat,
        placeable-free string needs no real offset translation."""
    def gui_to_tree_index(self, offset):
        return offset


class _FakeTextbox:
    def __init__(self, text):
        self.elem = StringElem(text)
        self.elem.gui_info = _FakeGuiInfo()
        self.refresh_cursor_pos = -1
        # Mimics the real widget: only moves once refresh() actually
        # runs - which undocontroller.py defers via GLib.idle_add, so a
        # test driving multiple steps without pumping the main loop
        # models a chain outrunning that deferred flush.
        self._rendered_cursor_pos = len(text)

    def get_cursor_position(self):
        return self._rendered_cursor_pos

    def refresh(self, update=True):
        if self.refresh_cursor_pos >= 0:
            self._rendered_cursor_pos = self.refresh_cursor_pos
        self.refresh_cursor_pos = -1


class _FakeView:
    def __init__(self, textbox, unit):
        self.targets = [textbox]
        self.unit = unit

    def disable_signals(self):
        pass

    def enable_signals(self):
        pass


class _FakeUnit:
    STATE = None


class _FakeUnitController:
    def __init__(self, textbox, unit):
        self.view = _FakeView(textbox, unit)
        self.current_unit = unit
        self.restored_states = []  # [(state, sticky), ...]
        self.set_states = []  # [state, ...], from set_current_state()

    def connect(self, signal, handler):
        pass

    def set_current_state(self, newstate, from_user=False):
        self.current_unit.state = newstate
        self.set_states.append(newstate)

    def restore_state(self, state, sticky):
        self.current_unit.state = state
        self.restored_states.append((state, sticky))

    def _correct_empty_state(self, unit):
        pass  # _correct_state_after_undo_redo()'s own re-check; not under test here


class _FakeStoreController:
    store = object()

    def __init__(self):
        self.stats_updated = []

    def set_modified(self, modified):
        pass

    def update_unit_stats(self, unit):
        self.stats_updated.append(unit)

    def connect(self, signal, handler):
        pass


class _FakeMainController:
    def __init__(self):
        self.store_controller = _FakeStoreController()

    def select_unit(self, unit, force=False):
        pass


class _FakeMenuItem:
    def set_sensitive(self, sensitive):
        pass

    def set_accel_path(self, path):
        pass

    def set_accel_group(self, group):
        pass

    def connect(self, signal, handler):
        pass


class _FakeMainViewGui:
    def __init__(self, widgets):
        self._widgets = widgets

    def get_object(self, name):
        return self._widgets[name]


class _FakeMainView:
    def __init__(self):
        self.gui = _FakeMainViewGui({
            'menu_edit': _FakeMenuItem(),
            'mnu_undo': _FakeMenuItem(),
            'mnu_redo': _FakeMenuItem(),
        })

    def add_accel_group(self, group):
        pass

    def sync_menubar(self):
        pass


def _make_controller(textbox, unit):
    controller = UndoController.__new__(UndoController)
    controller.enabled = True
    controller.model = UndoModel(controller)
    controller._pending_refresh = None
    controller.main_controller = _FakeMainController()
    controller.unit_controller = _FakeUnitController(textbox, unit)
    controller.mnu_undo = _FakeMenuItem()
    controller.mnu_redo = _FakeMenuItem()
    return controller


def test_undo_then_redo_round_trips_a_textboxs_text():
    textbox = _FakeTextbox('hello')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)

    controller.push_current_text(textbox)  # records "hello" as the undo target
    textbox.elem.sub = StringElem('hello world').sub  # the actual edit

    controller._on_undo_activated()
    assert str(textbox.elem) == 'hello'

    controller._on_redo_activated()
    assert str(textbox.elem) == 'hello world'


def test_undo_and_redo_refresh_the_units_state_lists():
    # Otherwise a mode chosen before leaving the unit misses its new
    # state (#4001).
    textbox = _FakeTextbox('')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)
    store_controller = controller.main_controller.store_controller

    controller.push_current_text(textbox)
    textbox.elem.sub = StringElem('Klaar').sub
    controller._on_undo_activated()
    controller._on_redo_activated()

    assert store_controller.stats_updated == [unit, unit]


def test_redo_does_nothing_when_the_redo_stack_is_empty():
    textbox = _FakeTextbox('hello')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)

    controller._on_redo_activated()

    assert str(textbox.elem) == 'hello'


def test_a_fresh_edit_after_undo_clears_redo():
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)

    controller.push_current_text(textbox)
    textbox.elem.sub = StringElem('ab').sub
    controller._on_undo_activated()
    assert str(textbox.elem) == 'a'

    controller.push_current_text(textbox)  # a genuinely new edit, not a redo
    textbox.elem.sub = StringElem('ax').sub

    controller._on_redo_activated()
    assert str(textbox.elem) == 'ax'  # unchanged - nothing left to redo


def test_undo_snapshots_the_unit_actually_undone_not_whatever_is_on_screen():
    # targets[] is one reused textbox widget - undoing unit A while unit B
    # is on screen must snapshot A's own state for redo, not B's.
    textbox = _FakeTextbox('A1')
    unit_a, unit_b = _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)
    content = {unit_a: 'A1', unit_b: 'B1'}

    def select_unit(unit, force=False):
        view = controller.unit_controller.view
        content[view.unit] = str(textbox.elem)
        view.unit = unit
        controller.unit_controller.current_unit = unit
        textbox.elem = StringElem(content[unit])
    controller.main_controller.select_unit = select_unit

    controller.push_current_text(textbox)
    textbox.elem = StringElem('A2')

    select_unit(unit_b)
    controller.push_current_text(textbox)
    textbox.elem = StringElem('B2')

    controller._on_undo_activated()  # B2 -> B1
    controller._on_undo_activated()  # navigate back to A (no text change)
    controller._on_undo_activated()  # A2 -> A1

    controller._on_redo_activated()  # A1 -> A2
    assert str(textbox.elem) == 'A2'

    controller._on_redo_activated()  # navigate forward to B
    controller._on_redo_activated()  # B1 -> B2
    assert str(textbox.elem) == 'B2'


def test_correct_state_after_undo_redo_updates_modified_flag():
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)
    modified_calls = []
    controller.main_controller.store_controller.set_modified = modified_calls.append
    controller.model.mark_clean()

    controller.push_current_text(textbox)
    textbox.elem.sub = StringElem('ab').sub

    controller._on_undo_activated()
    assert modified_calls[-1] is False

    controller._on_redo_activated()
    assert modified_calls[-1] is True


def test_sensitivity_reflects_undo_redo_stack_state():
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)
    undo_calls, redo_calls = [], []
    controller.mnu_undo.set_sensitive = undo_calls.append
    controller.mnu_redo.set_sensitive = redo_calls.append

    controller._update_sensitivity()
    assert (undo_calls[-1], redo_calls[-1]) == (False, False)

    controller.push_current_text(textbox)
    assert (undo_calls[-1], redo_calls[-1]) == (True, False)

    textbox.elem.sub = StringElem('ab').sub
    controller._on_undo_activated()
    assert (undo_calls[-1], redo_calls[-1]) == (False, True)

    controller._on_redo_activated()
    assert (undo_calls[-1], redo_calls[-1]) == (True, False)


def test_typing_updates_sensitivity():
    # Real per-keystroke edits go through _on_unit_insert_text /
    # _on_unit_delete_text, a separate path from push_current_text()
    # that must update sensitivity itself.
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)
    undo_calls = []
    controller.mnu_undo.set_sensitive = undo_calls.append

    controller._on_unit_insert_text(None, unit, 'x', 0, textbox.elem, 0)

    assert undo_calls[-1] is True


def test_push_state_change_updates_sensitivity():
    # UnitController.set_current_state()'s own from_user branch used to
    # push straight to model.push(), skipping this - the Undo menu item
    # (and its Cmd+Z accelerator, which GTK won't activate on an
    # insensitive item) stayed disabled after a deliberate state change
    # until some unrelated later push happened to refresh it, making
    # undo appear to do nothing at all.
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)
    undo_calls = []
    controller.mnu_undo.set_sensitive = undo_calls.append

    controller.push_state_change(unit, 80, False, 100)

    assert undo_calls[-1] is True


def test_chained_undo_redo_uses_each_edits_own_recorded_cursor_position():
    # _perform_undo()'s own cursor restore is deferred (GLib.idle_add) -
    # a chained undo/redo faster than that must not rely on a live
    # widget read, which can still be showing an earlier step's state.
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)

    controller._on_unit_insert_text(None, unit, 'b', 1, textbox.elem, 0)
    textbox.elem.sub = StringElem('ab').sub
    controller._on_unit_insert_text(None, unit, 'c', 2, textbox.elem, 0)
    textbox.elem.sub = StringElem('abc').sub

    controller._on_undo_activated()  # abc -> ab (deferred refresh never runs)
    controller._on_undo_activated()  # ab -> a

    # redo_stack[1] is the 'b' edit's own redo entry, built while the
    # widget was still showing the 'c' edit's not-yet-flushed cursor.
    redo_of_b = controller.model.redo_stack[1]
    assert redo_of_b['cursorpos'] == 2  # right after 'b'


def test_redo_cursor_position_survives_a_unit_switch():
    # _select_unit() reloading a reused widget for a different unit can
    # reset its live cursor to that reload's own default - not the
    # position this specific edit's redo should land on.
    textbox = _FakeTextbox('')
    unit_a, unit_b = _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)

    def select_unit(unit, force=False):
        controller.unit_controller.view.unit = unit
        controller.unit_controller.current_unit = unit
        textbox._rendered_cursor_pos = 0  # a fresh unit's own default
    controller.main_controller.select_unit = select_unit

    controller._on_unit_insert_text(None, unit_a, 'x', 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('x').sub

    select_unit(unit_b)
    controller._on_unit_insert_text(None, unit_b, 'y', 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('y').sub

    controller._on_undo_activated()  # undoes unit_b's 'y'
    controller._on_undo_activated()  # navigate back to A (no text change)
    controller._on_undo_activated()  # undoes unit_a's 'x'

    redo_of_a = controller.model.redo_stack[2]
    assert redo_of_a['cursorpos'] == 1  # right after 'x', not the reload's 0


def test_crossing_units_during_undo_flushes_the_earlier_units_pending_refresh(monkeypatch):
    # _schedule_cursor_restore()'s own refresh() is deferred via
    # GLib.idle_add(), which runs behind whatever input events are
    # already queued - a fast enough next undo/redo can switch units
    # before an earlier step's refresh() ever fires. In the real app
    # that refresh() is also what commits the edited text back to the
    # underlying translation unit (TextBox.refresh()'s own
    # set_text()/'changed' chain) - silently dropping it, not just its
    # cursor position. _select_unit() must flush it first.
    calls = []
    monkeypatch.setattr(undocontroller_module.GLib, 'idle_add', lambda func, *a: calls.append(func))
    textbox = _FakeTextbox('')
    unit_a, unit_b = _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)
    content = {unit_a: '', unit_b: ''}

    def select_unit(unit, force=False):
        view = controller.unit_controller.view
        content[view.unit] = str(textbox.elem)
        view.unit = unit
        controller.unit_controller.current_unit = unit
        textbox.elem = StringElem(content[unit])
        textbox.elem.gui_info = _FakeGuiInfo()
    controller.main_controller.select_unit = select_unit

    controller._on_unit_insert_text(None, unit_a, 'one', 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('one').sub

    select_unit(unit_b)
    controller._on_unit_insert_text(None, unit_b, 'B1', 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('B1').sub

    controller._on_undo_activated()  # reverts B1, schedules a refresh for B - GLib hasn't run it yet
    assert controller._pending_refresh is not None
    refresh_ran = []
    orig_refresh = textbox.refresh
    textbox.refresh = lambda *a, **kw: (refresh_ran.append(True), orig_refresh(*a, **kw))[-1]

    controller._on_undo_activated()  # navigates to A - must not strand B's still-queued refresh
    assert refresh_ran, "B's pending refresh (and whatever it commits) must run before switching away"


def test_undo_across_units_navigates_before_reverting():
    # translate/virtaal#2081: undoing across units must land on the
    # earlier unit first and revert its text on the next undo - not
    # jump and revert in the same keypress.
    textbox = _FakeTextbox('A1')
    unit_a, unit_b = _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)
    content = {unit_a: 'A1', unit_b: 'B1'}

    def select_unit(unit, force=False):
        view = controller.unit_controller.view
        content[view.unit] = str(textbox.elem)
        view.unit = unit
        controller.unit_controller.current_unit = unit
        textbox.elem = StringElem(content[unit])
    controller.main_controller.select_unit = select_unit

    controller.push_current_text(textbox)
    textbox.elem = StringElem('A2')

    select_unit(unit_b)
    controller.push_current_text(textbox)
    textbox.elem = StringElem('B2')

    controller._on_undo_activated()  # reverts B2 -> B1, stays on B
    assert controller.unit_controller.current_unit is unit_b
    assert str(textbox.elem) == 'B1'

    controller._on_undo_activated()  # navigates to A - text untouched
    assert controller.unit_controller.current_unit is unit_a
    assert str(textbox.elem) == 'A2'

    controller._on_undo_activated()  # reverts A2 -> A1
    assert str(textbox.elem) == 'A1'


def test_undo_across_units_restores_the_cursor_it_left_at(monkeypatch):
    # Landing back on a unit via navigate-undo used _select_unit()'s
    # own smart-start cursor default - confusing next to where the
    # user had actually left off editing that unit. Uses the real
    # typing path (_on_unit_insert_text) rather than push_current_text()
    # - only the former sets 'redo_cursorpos', which is the field this
    # is meant to use (the position *after* the edit, not before it -
    # a wrong choice here previously landed the cursor one character
    # early and went uncaught, since push_current_text() entries never
    # have a 'redo_cursorpos' to tell the two apart).
    calls = []
    monkeypatch.setattr(undocontroller_module.GLib, 'idle_add', lambda func, *a: calls.append(func))
    textbox = _FakeTextbox('')
    unit_a, unit_b = _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)
    content = {unit_a: '', unit_b: ''}

    def select_unit(unit, force=False):
        view = controller.unit_controller.view
        content[view.unit] = str(textbox.elem)
        view.unit = unit
        controller.unit_controller.current_unit = unit
        textbox.elem = StringElem(content[unit])
        textbox.elem.gui_info = _FakeGuiInfo()
        textbox._rendered_cursor_pos = 0  # a fresh unit's own smart-start default
    controller.main_controller.select_unit = select_unit

    controller._on_unit_insert_text(None, unit_a, 'one', 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('one').sub  # cursor now after "one", position 3

    select_unit(unit_b)
    controller._on_unit_insert_text(None, unit_b, 'B1', 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('B1').sub

    controller._on_undo_activated()  # reverts B1, stays on B
    controller._on_undo_activated()  # navigates to A

    assert calls, 'expected a deferred cursor-restore refresh() to be scheduled'
    calls[-1]()  # run it directly, same as this suite's other deferred-refresh tests
    assert textbox._rendered_cursor_pos == 3  # right after "one", not one character early


def test_undo_after_a_drifted_navigation_restores_the_cursor_it_left_at(monkeypatch):
    # The drift-resolution navigate-only step (_needs_navigation_first())
    # used _select_unit()'s own smart-start cursor default too - same bug
    # as the previous test, but for landing on a unit to resolve drift
    # rather than for a real navigate-kind undo.
    calls = []
    monkeypatch.setattr(undocontroller_module.GLib, 'idle_add', lambda func, *a: calls.append(func))
    textbox = _FakeTextbox('')
    unit_a, unit_b = _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)
    content = {unit_a: '', unit_b: ''}

    def select_unit(unit, force=False):
        view = controller.unit_controller.view
        content[view.unit] = str(textbox.elem)
        view.unit = unit
        controller.unit_controller.current_unit = unit
        textbox.elem = StringElem(content[unit])
        textbox.elem.gui_info = _FakeGuiInfo()
        textbox._rendered_cursor_pos = 0  # a fresh unit's own smart-start default
    controller.main_controller.select_unit = select_unit

    controller._on_unit_insert_text(None, unit_a, 'one', 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('one').sub  # cursor now after "one", position 3

    select_unit(unit_b)  # e.g. wrapping past the last unit - never pushed

    controller._on_undo_activated()  # resolves the drift, doesn't touch the stack yet
    assert controller.unit_controller.current_unit is unit_a

    assert calls, 'expected a deferred cursor-restore refresh() to be scheduled'
    calls[-1]()
    assert textbox._rendered_cursor_pos == 3  # right after "one", not the fresh-unit default


def test_undo_redo_of_a_deliberate_state_change():
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)
    controller.model.push({
        'kind': 'state', 'unit': unit, 'from_state': 80, 'from_sticky': False, 'to_state': 100,
    })

    controller._on_undo_activated()
    assert controller.unit_controller.restored_states[-1] == (80, False)

    controller._on_redo_activated()
    assert controller.unit_controller.restored_states[-1] == (100, True)


def test_undo_of_a_state_change_then_an_edit_elsewhere_navigates_first():
    # Ctrl+Enter's state advance (unit A) followed by editing unit B:
    # undoing must land back on A before reverting its state change,
    # the same two-step behaviour as a plain text edit gets.
    textbox = _FakeTextbox('B1')
    unit_a, unit_b = _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)

    def select_unit(unit, force=False):
        controller.unit_controller.view.unit = unit
        controller.unit_controller.current_unit = unit
    controller.main_controller.select_unit = select_unit

    controller.model.push({
        'kind': 'state', 'unit': unit_a, 'from_state': 80, 'from_sticky': False, 'to_state': 100,
    })
    select_unit(unit_b)
    controller.push_current_text(textbox)
    textbox.elem = StringElem('B2')

    controller._on_undo_activated()  # reverts B2 -> B1
    controller._on_undo_activated()  # navigates back to A - state untouched
    assert controller.unit_controller.current_unit is unit_a
    assert controller.unit_controller.restored_states == []

    controller._on_undo_activated()  # reverts A's state change
    assert controller.unit_controller.restored_states[-1] == (80, False)


def test_undo_after_a_pure_navigation_navigates_before_reverting():
    # Navigation is only ever pushed retroactively, between two pushed
    # acts (undomodel.py's push()) - Ctrl+Enter's own move to the next
    # unit is a pure focus change with no push of its own. Undoing must
    # still resolve that drift as its own step first, the same as any
    # other cross-unit undo - not combine it with reverting whatever's
    # actually on the stack in the same keypress.
    textbox = _FakeTextbox('A1')
    unit_a, unit_b = _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)

    def select_unit(unit, force=False):
        controller.unit_controller.view.unit = unit
        controller.unit_controller.current_unit = unit
    controller.main_controller.select_unit = select_unit

    controller.model.push({
        'kind': 'state', 'unit': unit_a, 'from_state': 80, 'from_sticky': False, 'to_state': 100,
    })
    select_unit(unit_b)  # e.g. Ctrl+Enter's own focus move - never pushed

    controller._on_undo_activated()
    assert controller.unit_controller.current_unit is unit_a  # resolves the drift...
    assert controller.unit_controller.restored_states == []  # ...without touching the stack yet

    controller._on_undo_activated()  # now actually reverts the state change
    assert controller.unit_controller.restored_states[-1] == (80, False)


def test_multiple_untracked_navigations_compact_into_one_undo_step():
    # Browsing through several units with no edits along the way must
    # not replay each hop as its own undo press - there's only the one
    # entry actually on the stack to land back on, however many
    # untracked hops happened after it.
    textbox = _FakeTextbox('A1')
    unit_a, unit_b, unit_c = _FakeUnit(), _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)

    def select_unit(unit, force=False):
        controller.unit_controller.view.unit = unit
        controller.unit_controller.current_unit = unit
    controller.main_controller.select_unit = select_unit

    controller.push_current_text(textbox)  # records 'A1' as the undo target
    textbox.elem = StringElem('A2')  # the actual edit

    select_unit(unit_b)  # browsing onward - neither hop is pushed
    select_unit(unit_c)

    controller._on_undo_activated()  # resolves the drift in one step, however far
    assert controller.unit_controller.current_unit is unit_a
    assert str(textbox.elem) == 'A2'  # not yet reverted

    controller._on_undo_activated()  # now actually reverts
    assert str(textbox.elem) == 'A1'


def test_redoing_a_navigation_moves_forward_regardless_of_current_position():
    # Unlike undo, redoing a navigate-kind entry always just moves
    # forward to wherever it goes - there's no "expected prior
    # position" to resolve first the way a text/state entry has.
    textbox = _FakeTextbox('A1')
    unit_a, unit_b, unit_c = _FakeUnit(), _FakeUnit(), _FakeUnit()
    controller = _make_controller(textbox, unit_a)
    content = {unit_a: 'A1', unit_b: 'B1'}

    def select_unit(unit, force=False):
        view = controller.unit_controller.view
        content[view.unit] = str(textbox.elem)
        view.unit = unit
        controller.unit_controller.current_unit = unit
        textbox.elem = StringElem(content.get(unit, ''))
    controller.main_controller.select_unit = select_unit

    controller.push_current_text(textbox)
    textbox.elem = StringElem('A2')
    select_unit(unit_b)
    controller.push_current_text(textbox)
    textbox.elem = StringElem('B2')

    controller._on_undo_activated()  # B2 -> B1
    controller._on_undo_activated()  # navigate back to A - pushes a navigate-kind redo entry
    assert controller.unit_controller.current_unit is unit_a

    select_unit(unit_c)  # browse somewhere else entirely before redoing
    controller._on_redo_activated()  # still just moves forward to B, unconditionally
    assert controller.unit_controller.current_unit is unit_b


def test_undo_of_a_text_edit_restores_its_bundled_state_change():
    # translate/virtaal#1886: undo must restore the state an edit's
    # own automatic correction changed, not just the text.
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    unit.STATE = True
    unit._current_state = 80  # e.g. fuzzy, before the edit
    controller = _make_controller(textbox, unit)

    controller._on_unit_delete_text(None, unit, StringElem('a'), None, 0, 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('').sub
    controller.model.attach_state_after(unit, 0)  # what _correct_empty_state() does next

    controller._on_undo_activated()
    assert str(textbox.elem) == 'a'
    assert controller.unit_controller.set_states[-1] == 80

    controller._on_redo_activated()
    assert str(textbox.elem) == ''
    assert controller.unit_controller.set_states[-1] == 0


def test_undo_of_a_bundled_state_change_survives_the_automatic_recheck(monkeypatch):
    # translate/virtaal#1886, a second bug in the same area:
    # _correct_state_after_undo_redo()'s own automatic empty/unreviewed
    # re-check reads unit.target - but the just-applied undo/redo
    # action's own text commit is still pending via GLib.idle_add() (see
    # _schedule_cursor_restore()), so it can see stale, not-yet-restored
    # content and silently override a state this same step just
    # restored via the bundled state_before/state_after mechanism.
    monkeypatch.setattr(undocontroller_module.GLib, 'idle_add', lambda func, *a: calls.append(func))
    calls = []
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    unit.STATE = True
    unit._current_state = 80  # fuzzy, before the edit
    unit.target = 'a'  # what the real _correct_empty_state() reads - lags
                        # behind textbox.elem until refresh() runs
    controller = _make_controller(textbox, unit)

    orig_refresh = textbox.refresh
    def refresh_and_commit(*a, **kw):
        orig_refresh(*a, **kw)
        unit.target = str(textbox.elem)  # what TextBox.refresh()'s own set_text()/'changed' chain does for real
    textbox.refresh = refresh_and_commit

    def correct_empty_state(u):
        # A faithful-enough stand-in for the real
        # UnitController._correct_empty_state(): EMPTY<->UNREVIEWED
        # based on u.target, not textbox.elem - that distinction is the
        # whole point of this test.
        target_len = len(u.target)
        empty_state = u._current_state == 0
        if target_len and empty_state:
            u._current_state = 999
        elif not target_len and not empty_state:
            u._current_state = 0
    controller.unit_controller._correct_empty_state = correct_empty_state

    controller._on_unit_delete_text(None, unit, StringElem('a'), None, 0, 0, textbox.elem, 0)
    textbox.elem.sub = StringElem('').sub
    unit.target = ''  # the debounced correction's own refresh already committed this by now
    controller.model.attach_state_after(unit, 0)

    controller._on_undo_activated()

    assert str(textbox.elem) == 'a'
    assert unit._current_state == 80  # the bundled restore must survive the automatic re-check


def test_init_disables_undo_redo_immediately():
    # Otherwise stuck at the .ui file's default (enabled) until a later
    # store-loaded/closed or edit event happens to fire - never, on a
    # welcome screen where no file's ever been opened this session.
    main_controller = _FakeMainController()
    main_controller.view = _FakeMainView()
    unit = _FakeUnit()
    textbox = _FakeTextbox('')
    main_controller.store_controller.unit_controller = _FakeUnitController(textbox, unit)
    main_controller.store_controller.store = None

    controller = UndoController.__new__(UndoController)
    undo_calls, redo_calls = [], []
    monkeypatch_undo = main_controller.view.gui.get_object('mnu_undo')
    monkeypatch_redo = main_controller.view.gui.get_object('mnu_redo')
    monkeypatch_undo.set_sensitive = undo_calls.append
    monkeypatch_redo.set_sensitive = redo_calls.append

    UndoController.__init__(controller, main_controller)

    assert undo_calls[-1] is False
    assert redo_calls[-1] is False
