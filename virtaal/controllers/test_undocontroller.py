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
    def set_modified(self, modified):
        pass


class _FakeMainController:
    def __init__(self):
        self.store_controller = _FakeStoreController()

    def select_unit(self, unit, force=False):
        pass


def _make_controller(textbox, unit):
    controller = UndoController.__new__(UndoController)
    controller.enabled = True
    controller.model = UndoModel(controller)
    controller.main_controller = _FakeMainController()
    controller.unit_controller = _FakeUnitController(textbox, unit)
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
