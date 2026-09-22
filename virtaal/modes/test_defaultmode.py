#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.modes.defaultmode import DefaultMode


def _mode(cursor):
    controller = SimpleNamespace(
        main_controller=SimpleNamespace(store_controller=SimpleNamespace(cursor=cursor))
    )
    return DefaultMode(controller)


def test_selected_does_nothing_without_a_cursor():
    mode = _mode(cursor=None)

    mode.selected()  # must not raise


def test_selected_does_nothing_without_a_cursor_model():
    mode = _mode(cursor=SimpleNamespace(model=None))

    mode.selected()  # must not raise


def test_selected_shows_every_unit():
    cursor = SimpleNamespace(model=SimpleNamespace(stats={'total': [0, 1, 2]}), indices=None)
    mode = _mode(cursor=cursor)

    mode.selected()

    assert cursor.indices == [0, 1, 2]


def test_unselected_does_nothing():
    mode = _mode(cursor=None)

    mode.unselected()  # must not raise
