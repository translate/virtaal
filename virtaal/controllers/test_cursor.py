#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest

from virtaal.controllers.cursor import Cursor


def _cursor(indices, model=None):
    cursor = Cursor(model if model is not None else list('abcdef'), indices)
    signals = []
    cursor.connect('cursor-changed', lambda c: signals.append('changed'))
    cursor.connect('cursor-empty', lambda c: signals.append('empty'))
    return cursor, signals


def test_emptying_indices_emits_cursor_empty_but_not_cursor_changed():
    cursor, signals = _cursor([1, 3])
    cursor.index = 3
    signals.clear()

    cursor.indices = []

    assert signals == ['empty']
    assert cursor.index == -1


def test_deref_of_an_empty_cursor_is_none_not_the_last_item():
    cursor, _signals = _cursor([])

    assert cursor.deref() is None


def test_move_on_an_empty_cursor_does_nothing():
    cursor, signals = _cursor([])

    cursor.move(1)
    cursor.move(-1)

    assert signals == []
    assert cursor.index == -1


def test_setting_index_on_an_empty_cursor_does_nothing():
    cursor, signals = _cursor([])

    cursor.index = 2

    assert signals == []
    assert cursor.index == -1


def test_refilling_indices_returns_near_the_unit_before_they_emptied():
    cursor, signals = _cursor([1, 3, 5])
    cursor.index = 3
    cursor.indices = []
    signals.clear()

    cursor.indices = [0, 4, 5]

    assert cursor.index == 4
    assert signals == ['changed']


def test_force_index_on_an_empty_cursor_visits_that_index():
    cursor, signals = _cursor([])

    cursor.force_index(2)

    assert cursor.indices == []
    assert cursor.index == 2
    assert cursor.deref() == 'c'
    assert signals == ['changed']


def test_changing_indices_keeps_the_current_unit_when_it_is_still_included():
    cursor, signals = _cursor([1, 3, 5])
    cursor.index = 3
    signals.clear()

    cursor.indices = [0, 3]

    assert cursor.index == 3


# visit() #

def test_visit_moves_to_a_unit_outside_indices_without_adding_it():
    cursor, signals = _cursor([1, 4])
    signals.clear()

    cursor.visit(2)

    assert cursor.index == 2
    assert cursor.deref() == 'c'
    assert cursor.indices == [1, 4]
    assert signals == ['changed']


def test_visit_of_an_index_in_indices_is_a_normal_move():
    cursor, _signals = _cursor([1, 4])

    cursor.visit(4)
    cursor.move(1)

    assert cursor.index == 1  # wrapped: 4 was a real position


def test_moving_on_from_a_visit_goes_to_the_next_unit_in_indices():
    cursor, _signals = _cursor([1, 4])
    cursor.visit(2)

    cursor.move(1)

    assert cursor.index == 4


def test_moving_back_from_a_visit_goes_to_the_previous_unit_in_indices():
    cursor, _signals = _cursor([1, 4])
    cursor.visit(2)

    cursor.move(-1)

    assert cursor.index == 1


def test_moving_on_from_a_visit_after_the_last_unit_wraps():
    cursor, _signals = _cursor([1, 4])
    cursor.visit(5)

    cursor.move(1)

    assert cursor.index == 1


def test_moving_back_from_a_visit_before_the_first_unit_wraps():
    cursor, _signals = _cursor([1, 4])
    cursor.visit(0)

    cursor.move(-1)

    assert cursor.index == 4


def test_setting_index_ends_a_visit():
    cursor, signals = _cursor([1, 4])
    cursor.index = 1
    cursor.visit(2)
    signals.clear()

    cursor.index = 1

    assert cursor.index == 1
    assert signals == ['changed']


def test_new_indices_keep_the_cursor_on_the_visited_unit():
    # E.g. search re-running while the visited unit is being edited.
    cursor, signals = _cursor([1, 4])
    cursor.visit(2)
    signals.clear()

    cursor.indices = [0, 4]

    assert cursor.index == 2
    assert signals == []


def test_new_indices_including_the_visited_unit_end_the_visit():
    cursor, _signals = _cursor([1, 4])
    cursor.visit(2)

    cursor.indices = [1, 2, 4]
    cursor.move(1)

    assert cursor.index == 4


def _positioned_cursor(n, pos, circular):
    cursor = Cursor(None, list(range(n)), circular=circular)
    cursor.pos = pos
    changes = []
    cursor.connect('cursor-changed', lambda *args: changes.append(cursor.pos))
    return cursor, changes


@pytest.mark.parametrize('n, pos, offset, expected', [
    (5, 1, 1, 2),
    (5, 1, -1, 0),
    (5, 4, 1, 4),
    (5, 0, -1, 0),
    (5, 2, 10, 4),
    (5, 2, -10, 0),
    (1, 0, 1, 0),
])
def test_move_stops_at_the_ends(n, pos, offset, expected):
    cursor, _changes = _positioned_cursor(n, pos, circular=False)
    cursor.move(offset)
    assert cursor.pos == expected


def test_move_at_the_end_does_not_emit_cursor_changed():
    cursor, changes = _positioned_cursor(5, 4, circular=False)
    cursor.move(1)
    cursor.move(10)
    assert changes == []


@pytest.mark.parametrize('n, pos, offset, expected', [
    (5, 4, 1, 0),
    (5, 0, -1, 4),
    (5, 3, 2, 0),
    (5, 4, 5, 4),
    # Offsets larger than the list, such as PageDown on a short list (#3789).
    (3, 2, 10, 0),
    (3, 0, -10, 2),
    (7, 5, 10, 1),
    (7, 2, -10, 6),
])
def test_move_circular_wraps(n, pos, offset, expected):
    cursor, _changes = _positioned_cursor(n, pos, circular=True)
    cursor.move(offset)
    assert cursor.pos == expected


@pytest.mark.parametrize('visiting, offset, circular, expected', [
    (6, 1, False, 8),
    (6, -1, False, 5),
    (9, 1, False, 8),
    (1, -1, False, 2),
    (6, 10, False, 8),
    (9, 1, True, 2),
    (1, -1, True, 8),
])
def test_move_from_a_visited_unit(visiting, offset, circular, expected):
    cursor = Cursor(None, [2, 5, 8], circular=circular)
    cursor.visit(visiting)
    cursor.move(offset)
    assert cursor.index == expected
