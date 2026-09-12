#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views.widgets.selectview import SelectView


def _make_view():
    return SelectView(items=[{'name': 'A', 'enabled': True}, {'name': 'B', 'enabled': True}])


def test_selection_change_does_not_start_editing(monkeypatch):
    # Arrow-key navigation changes the selection without activating the
    # row - starting editing here stole focus into the row's embedded
    # widget, leaving Up/Down with nothing left to navigate.
    sview = _make_view()
    calls = []
    monkeypatch.setattr(sview, 'set_cursor', lambda *a, **k: calls.append((a, k)))

    sview.get_selection().select_path(Gtk.TreePath.new_from_indices([1]))

    assert calls == []


def test_row_activated_still_starts_editing(monkeypatch):
    sview = _make_view()
    calls = []
    monkeypatch.setattr(sview, 'set_cursor', lambda *a, **k: calls.append((a, k)))

    sview.do_row_activated(Gtk.TreePath.new_from_indices([0]), sview.namedesc_col)

    assert calls
