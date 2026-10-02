#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


from types import SimpleNamespace

import pytest

from virtaal.common import pan_app
from virtaal.views import storeview
from virtaal.views.storeview import CONTEXT_ALL, StoreView, visible_units

# visible_units() #


def test_visible_units_shows_matches_and_context_around_the_current_unit():
    assert visible_units([2, 9], 9, 1, 20) == [2, 8, 9, 10]


def test_visible_units_with_no_context_shows_only_the_matches_and_current_unit():
    assert visible_units([2, 9], 5, 0, 20) == [2, 5, 9]


def test_visible_units_clips_context_at_the_ends_of_the_file():
    assert visible_units([0, 19], 0, 3, 20) == [0, 1, 2, 3, 19]
    assert visible_units([0, 19], 19, 3, 20) == [0, 16, 17, 18, 19]


def test_visible_units_is_empty_with_no_matches_and_no_current_unit():
    assert visible_units([], -1, 2, 20) == []


def test_visible_units_shows_everything_for_all_context_or_when_everything_matches():
    assert visible_units([2], 2, CONTEXT_ALL, 20) is None
    assert visible_units(list(range(20)), 5, 1, 20) is None


# context setting #

@pytest.fixture
def general_settings(monkeypatch):
    general = {}
    monkeypatch.setattr(pan_app.settings, 'general', general)
    return general


def test_context_setting_defaults_to_all(general_settings):
    assert storeview.load_context_setting() is CONTEXT_ALL


def test_context_setting_round_trips(general_settings):
    storeview.save_context_setting(2)
    assert general_settings[storeview.CONTEXT_SETTING] == '2'
    assert storeview.load_context_setting() == 2

    storeview.save_context_setting(CONTEXT_ALL)
    assert storeview.load_context_setting() is CONTEXT_ALL


# StoreView._update_visible_rows() #

def _view(indices, index, context, change=None):
    view = StoreView.__new__(StoreView)
    view.store = ['u'] * 10
    view.cursor = SimpleNamespace(indices=indices, index=index)
    view.context = context
    view._updating_rows = False
    view._rows_outdated = False
    calls = []
    view._treeview = SimpleNamespace(
        set_visible_rows=lambda rows: calls.append(('rows', rows)) or change,
        select_index=lambda index, force=False: calls.append(('select', index) + (('force',) if force else ())),
        refresh_current_row=lambda: calls.append(('refresh',)),
    )
    return view, calls


def test_update_visible_rows_shows_the_matches_and_context():
    view, calls = _view([1, 7], 7, 1)

    view._update_visible_rows()

    assert calls == [('rows', [1, 6, 7, 8])]


def test_update_visible_rows_restarts_editing_after_a_rebuild():
    view, calls = _view([1, 7], 7, 0, change='rebuilt')

    view._update_visible_rows()

    assert calls == [('rows', [1, 7]), ('select', 7)]


def test_update_visible_rows_without_a_file_does_nothing():
    view, calls = _view([1], 1, 1)
    view.store = None

    view._update_visible_rows()

    assert calls == []


def test_set_context_saves_it_and_updates_the_rows(general_settings):
    view, calls = _view([1, 7], 1, 2)

    view.set_context(0)

    assert view.context == 0
    assert general_settings[storeview.CONTEXT_SETTING] == '0'
    assert calls == [('rows', [1, 7])]


def test_update_visible_rows_asked_again_mid_update_redoes_it_after():
    view, calls = _view([1, 7], 7, 0)

    def set_visible_rows(rows):
        calls.append(('rows', rows))
        if len(calls) == 1:
            view.cursor.index = 1  # a nested cursor move
            view._update_visible_rows()
        return None
    view._treeview.set_visible_rows = set_visible_rows

    view._update_visible_rows()

    assert calls == [('rows', [1, 7]), ('rows', [1, 7])]


def test_update_visible_rows_restarts_editing_after_rows_change_around_it():
    # GTK stops editing when rows are inserted or deleted.
    view, calls = _view([1, 7], 7, 1, change='changed')

    view._update_visible_rows()

    assert calls == [('rows', [1, 6, 7, 8]), ('refresh',)]


def test_cursor_moves_that_change_rows_force_editing_to_restart():
    # GTK cancels editing when rows are deleted, and may already have moved
    # its own cursor onto the new unit.
    view, calls = _view([1, 7], 7, 1, change='changed')

    view._on_cursor_change(view.cursor)

    assert calls == [('rows', [1, 6, 7, 8]), ('select', 7, 'force')]


def test_cursor_moves_with_no_row_change_select_normally():
    view, calls = _view([1, 7], 7, 1, change=None)

    view._on_cursor_change(view.cursor)

    assert calls == [('rows', [1, 6, 7, 8]), ('select', 7)]
