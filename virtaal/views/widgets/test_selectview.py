#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gdk, Gtk

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


def test_space_toggles_the_enabled_state_at_the_cursor_row():
    # GTK's own Space handling only reaches the Enabled checkbox if
    # the cursor's focus column happens to be that one - it's always
    # namedesc_col here once a row's been activated, so Space silently
    # did nothing.
    sview = _make_view()
    sview.set_cursor(Gtk.TreePath.new_from_indices([0]))
    before = sview.get_all_items()[0]['enabled']

    sview._on_key_press(sview, SimpleNamespace(keyval=Gdk.KEY_space))

    assert sview.get_all_items()[0]['enabled'] != before


def test_enter_activates_the_cursor_row(monkeypatch):
    sview = _make_view()
    sview.set_cursor(Gtk.TreePath.new_from_indices([0]))
    calls = []
    monkeypatch.setattr(sview, 'set_cursor', lambda *a, **k: calls.append((a, k)))

    sview._on_key_press(sview, SimpleNamespace(keyval=Gdk.KEY_Return))

    assert calls


def test_other_keys_are_left_to_the_default_handling():
    sview = _make_view()
    sview.set_cursor(Gtk.TreePath.new_from_indices([0]))

    handled = sview._on_key_press(sview, SimpleNamespace(keyval=Gdk.KEY_Down))

    assert handled is False


def test_select_item_finds_a_row_that_is_not_the_first():
    # The search loop never advanced its iterator past the first row -
    # selecting anything else spun forever (confirmed live: 100% CPU,
    # the process never returning). Sorted by name, "B" is the second
    # of the two rows _make_view() creates.
    sview = _make_view()
    target = sview.get_all_items()[1]

    sview.select_item(target)

    assert sview.get_selected_item() == target


def test_configure_button_responds_to_the_clicked_signal():
    # Enter/Space on a focused button fires 'clicked' - the button
    # used to only listen for 'button-release-event', which a real
    # mouse click fires but keyboard activation never does.
    sview = _make_view()
    calls = []
    item = {'name': 'A', 'config': lambda parent: calls.append(parent)}
    widget = sview._create_widget_for_item(item)
    button = widget.get_children()[-1]

    button.emit('clicked')

    assert calls
