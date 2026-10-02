#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


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
