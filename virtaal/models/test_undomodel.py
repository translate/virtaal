#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.models.undomodel import UndoModel


def _noop(unit):
    pass


def _entry(n):
    return {'action': _noop, 'unit': n, 'targetn': 0, 'cursorpos': 0}


def test_pop_redo_on_an_empty_stack_returns_none():
    model = UndoModel(controller=None)

    assert model.pop_redo() is None


def test_undo_then_redo_restores_the_same_index():
    model = UndoModel(controller=None)
    model.push(_entry(1))
    model.push(_entry(2))

    model.pop()
    model.push_redo(_entry('redo-of-2'))
    assert model.index == 0

    redone = model.pop_redo()
    assert redone == _entry('redo-of-2')
    assert model.index == 1


def test_redo_stack_pops_in_lifo_order_across_multiple_undos():
    model = UndoModel(controller=None)
    model.push(_entry(1))
    model.push(_entry(2))

    model.pop()
    model.push_redo(_entry('redo-of-2'))
    model.pop()
    model.push_redo(_entry('redo-of-1'))

    assert model.pop_redo() == _entry('redo-of-1')
    assert model.pop_redo() == _entry('redo-of-2')
    assert model.pop_redo() is None


def test_a_fresh_push_clears_the_redo_stack():
    model = UndoModel(controller=None)
    model.push(_entry(1))
    model.pop()
    model.push_redo(_entry('redo-of-1'))

    model.push(_entry(2))

    assert model.pop_redo() is None


def test_record_start_clears_the_redo_stack():
    model = UndoModel(controller=None)
    model.push(_entry(1))
    model.pop()
    model.push_redo(_entry('redo-of-1'))

    model.record_start()
    model.record_stop()

    assert model.pop_redo() is None


def test_clear_empties_the_redo_stack():
    model = UndoModel(controller=None)
    model.push(_entry(1))
    model.pop()
    model.push_redo(_entry('redo-of-1'))

    model.clear()

    assert model.pop_redo() is None


def test_can_undo_and_can_redo_track_stack_state():
    model = UndoModel(controller=None)
    assert not model.can_undo()
    assert not model.can_redo()

    model.push(_entry(1))
    assert model.can_undo()
    assert not model.can_redo()

    model.pop()
    model.push_redo(_entry('redo-of-1'))
    assert not model.can_undo()
    assert model.can_redo()

    model.pop_redo()
    assert model.can_undo()
    assert not model.can_redo()
