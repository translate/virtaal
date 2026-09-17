#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.storage.placeables import StringElem

from virtaal.controllers.undocontroller import UndoController
from virtaal.models.undomodel import UndoModel


class _FakeTextbox:
    def __init__(self, text):
        self.elem = StringElem(text)
        self.refresh_cursor_pos = None

    def get_cursor_position(self):
        return len(str(self.elem))

    def refresh(self, update=True):
        pass


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


class _FakeStoreController:
    store = object()

    def set_modified(self, modified):
        pass


class _FakeMainController:
    def __init__(self):
        self.store_controller = _FakeStoreController()

    def select_unit(self, unit, force=False):
        pass


class _FakeMenuItem:
    def set_sensitive(self, sensitive):
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
