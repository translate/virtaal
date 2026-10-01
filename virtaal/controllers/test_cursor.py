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


def test_force_index_on_an_empty_cursor_selects_that_index():
    cursor, signals = _cursor([])

    cursor.force_index(2)

    assert cursor.indices == [2]
    assert cursor.index == 2
    assert 'changed' in signals


def test_changing_indices_keeps_the_current_unit_when_it_is_still_included():
    cursor, signals = _cursor([1, 3, 5])
    cursor.index = 3
    signals.clear()

    cursor.indices = [0, 3]

    assert cursor.index == 3
