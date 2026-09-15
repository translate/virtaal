#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from virtaal.views.widgets.storetreemodel import StoreTreeModel
from virtaal.views.widgets.storetreeview import StoreTreeView


class _FakeColumn:
    def __init__(self, width):
        self._width = width

    def get_fixed_width(self):
        return self._width

    def set_fixed_width(self, width):
        self._width = width


def _make_view(column_width, cursor):
    column = _FakeColumn(column_width)
    calls = []
    view = SimpleNamespace(
        get_columns=lambda: [column],
        get_cursor=lambda: cursor,
        set_cursor=lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    return view, column, calls


def test_on_size_allocate_restarts_editing_the_current_row_when_the_width_changes():
    # A FIXED column doesn't renegotiate row heights on its own when
    # its width changes - most visible on the very first allocation,
    # where the toplevel isn't realized yet and do_get_size() measures
    # the current row against a bogus ~1px width (#3526). Confirmed
    # live: queue_resize() alone didn't fix it, re-running the same
    # start_editing cursor cycle select_index() uses on a manual
    # navigation does.
    path, editcol = object(), object()
    view, column, calls = _make_view(column_width=1, cursor=(path, editcol))
    allocation = SimpleNamespace(width=800)

    StoreTreeView._on_size_allocate(view, None, allocation)

    assert column.get_fixed_width() == 798
    assert calls == [((path, editcol), {'start_editing': True})]


def test_on_size_allocate_is_a_noop_when_the_width_is_unchanged():
    path, editcol = object(), object()
    view, column, calls = _make_view(column_width=798, cursor=(path, editcol))
    allocation = SimpleNamespace(width=800)

    StoreTreeView._on_size_allocate(view, None, allocation)

    assert calls == []


def test_on_size_allocate_does_nothing_extra_without_a_current_row():
    view, column, calls = _make_view(column_width=1, cursor=(None, None))
    allocation = SimpleNamespace(width=800)

    StoreTreeView._on_size_allocate(view, None, allocation)

    assert column.get_fixed_width() == 798
    assert calls == []


def test_refresh_current_row_redoes_the_editing_cycle_in_place():
    # A one-shot set_cursor(start_editing=True) restarted editing but
    # left the row's terminology highlighting unrendered - select_index()
    # only ever gets the highlighting right by also calling
    # set_editable() and repeating set_cursor() once more on idle
    # (#3240). refresh_current_row() drives that same full cycle for
    # the already-current row, which select_index() itself skips.
    model = StoreTreeModel(['unit0'])
    path = Gtk.TreePath((0,))
    column = _FakeColumn(1)
    calls = []
    view = SimpleNamespace(
        get_model=lambda: model,
        get_columns=lambda: [column],
        get_cursor=lambda: (path, column),
        set_cursor=lambda *args, **kwargs: calls.append((args, kwargs)),
        _waiting_for_row_change=0,
    )
    view._start_editing_cycle = lambda *a, **kw: StoreTreeView._start_editing_cycle(view, *a, **kw)

    StoreTreeView.refresh_current_row(view)

    assert calls == [((path, column), {'start_editing': True})]
    assert view._waiting_for_row_change == 1


def test_refresh_current_row_does_nothing_without_a_current_row():
    model = StoreTreeModel([])
    calls = []
    view = SimpleNamespace(
        get_model=lambda: model,
        get_cursor=lambda: (None, None),
        set_cursor=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    StoreTreeView.refresh_current_row(view)

    assert calls == []
