#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.storage.placeables import StringElem

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
        self.emitted = []

    def connect(self, signal, handler):
        pass

    def emit(self, signal, *args):
        self.emitted.append((signal, *args))


class _FakeStoreController:
    store = object()

    def set_modified(self, modified):
        pass

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
    controller._on_undo_activated()  # A2 -> A1

    controller._on_redo_activated()  # A1 -> A2
    assert str(textbox.elem) == 'A2'

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


def test_correct_state_after_undo_redo_announces_unit_done():
    # Undo/redo reverts a unit's translation without ever going through
    # UnitView's normal edit-tracking signals (see _perform_undo()'s own
    # disable_signals()/enable_signals() around the revert) - anything
    # listening for 'unit-done' (e.g. the nav ribbon) would otherwise
    # never learn the unit's state changed.
    textbox = _FakeTextbox('a')
    unit = _FakeUnit()
    controller = _make_controller(textbox, unit)

    controller._correct_state_after_undo_redo()

    assert controller.unit_controller.emitted == [('unit-done', unit, True)]


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
    controller._on_undo_activated()  # undoes unit_a's 'x' - switches back to A first

    redo_of_a = controller.model.redo_stack[1]
    assert redo_of_a['cursorpos'] == 1  # right after 'x', not the reload's 0


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
