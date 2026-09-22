#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.modes.quicktransmode import QuickTranslateMode


def _mode(cursor, select_default_mode=None):
    controller = SimpleNamespace(
        main_controller=SimpleNamespace(store_controller=SimpleNamespace(cursor=cursor)),
        select_default_mode=select_default_mode or (lambda: None),
    )
    return QuickTranslateMode(controller)


def test_selected_does_nothing_without_a_cursor():
    mode = _mode(cursor=None)

    mode.selected()  # must not raise


def test_selected_does_nothing_without_a_cursor_model():
    mode = _mode(cursor=SimpleNamespace(model=None))

    mode.selected()  # must not raise


def test_selected_falls_back_to_default_mode_when_nothing_is_incomplete():
    cursor = SimpleNamespace(model=SimpleNamespace(stats={'untranslated': [], 'fuzzy': []}))
    calls = []
    mode = _mode(cursor=cursor, select_default_mode=lambda: calls.append(True))

    mode.selected()

    assert calls == [True]


def test_selected_shows_untranslated_and_fuzzy_units():
    cursor = SimpleNamespace(
        model=SimpleNamespace(stats={'untranslated': [2, 0], 'fuzzy': [1]}),
        indices=None,
    )
    mode = _mode(cursor=cursor)

    mode.selected()

    assert cursor.indices == [0, 1, 2]


def test_unselected_does_nothing():
    mode = _mode(cursor=None)

    mode.unselected()  # must not raise
