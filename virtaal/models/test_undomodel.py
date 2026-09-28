#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.models.undomodel import UndoModel


def _noop(unit):
    pass


_UNIT = object()  # a single shared unit - these tests are about stack
                   # mechanics, not navigation between units


def _entry(n):
    return {'action': _noop, 'unit': _UNIT, 'targetn': 0, 'cursorpos': 0, 'id': n}


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


def _entry_for(unit, n):
    return {'action': _noop, 'unit': unit, 'targetn': 0, 'cursorpos': 0, 'id': n}


def test_push_inserts_a_navigation_entry_between_different_units():
    model = UndoModel(controller=None)
    unit_a, unit_b = object(), object()
    model.push(_entry_for(unit_a, 'a1'))

    model.push(_entry_for(unit_b, 'b1'))

    assert [e.get('id', e.get('kind')) for e in model.undo_stack] == ['a1', 'navigate', 'b1']
    nav = model.undo_stack[1]
    assert nav == {'kind': 'navigate', 'unit': unit_b, 'from_unit': unit_a}


def test_push_inserts_no_navigation_entry_for_the_same_unit():
    model = UndoModel(controller=None)
    unit = object()
    model.push(_entry_for(unit, 'a1'))

    model.push(_entry_for(unit, 'a2'))

    assert len(model.undo_stack) == 2


def test_push_inserts_no_navigation_entry_for_the_very_first_edit():
    model = UndoModel(controller=None)

    model.push(_entry_for(object(), 'a1'))

    assert len(model.undo_stack) == 1


def test_clear_resets_navigation_tracking():
    model = UndoModel(controller=None)
    model.push(_entry_for(object(), 'a1'))
    model.clear()

    model.push(_entry_for(object(), 'b1'))

    assert len(model.undo_stack) == 1


def test_push_after_a_full_undo_does_not_insert_a_stale_navigation_entry():
    # A fresh edit after fully undoing everything wipes the stack (see
    # push()'s own `if self.index < 0` branch) - but _last_pushed_unit
    # used to survive that wipe untouched, so the next push (even to a
    # totally different unit) could still trigger a bogus navigation
    # entry pointing at a unit nothing on the now-empty stack actually
    # connects to.
    model = UndoModel(controller=None)
    unit_a, unit_b, unit_c = object(), object(), object()
    model.push(_entry_for(unit_a, 'a1'))
    model.push(_entry_for(unit_b, 'b1'))  # inserts NAV(a->b); _last_pushed_unit becomes unit_b

    model.pop()  # undoes b1
    model.pop()  # undoes NAV(a->b)
    model.pop()  # undoes a1
    assert model.index == -1

    model.push(_entry_for(unit_c, 'c1'))

    assert [e.get('id', e.get('kind')) for e in model.undo_stack] == ['c1']


def test_record_start_after_a_full_undo_does_not_insert_a_stale_navigation_entry():
    model = UndoModel(controller=None)
    unit_a, unit_b, unit_c = object(), object(), object()
    model.push(_entry_for(unit_a, 'a1'))
    model.push(_entry_for(unit_b, 'b1'))

    model.pop()
    model.pop()
    model.pop()
    assert model.index == -1

    model.record_start()
    model.push(_entry_for(unit_c, 'c1'))
    model.record_stop()

    assert [e.get('id', e.get('kind')) for e in model.undo_stack] == ['c1']


def test_record_start_group_gets_a_navigation_entry_before_it():
    model = UndoModel(controller=None)
    unit_a, unit_b = object(), object()
    model.push(_entry_for(unit_a, 'a1'))

    model.record_start()
    model.push(_entry_for(unit_b, 'b1'))
    model.push(_entry_for(unit_b, 'b2'))
    model.record_stop()

    assert len(model.undo_stack) == 3
    assert model.undo_stack[1] == {'kind': 'navigate', 'unit': unit_b, 'from_unit': unit_a}
    assert model.undo_stack[2] == [_entry_for(unit_b, 'b1'), _entry_for(unit_b, 'b2')]
