#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

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
