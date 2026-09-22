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
    return SelectView(items=[
        {'name': 'A', 'enabled': True, 'data': 'a'},
        {'name': 'B', 'enabled': True, 'data': 'b'},
    ])


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


def test_enter_calls_config_directly_when_the_row_has_one():
    # Configure... only exists as a real widget once the row's in
    # GTK's editing state - calling straight through on Enter matches
    # what a mouse click on the button itself already does, instead of
    # needing a second press once editing starts.
    calls = []
    sview = SelectView(items=[{'name': 'A', 'enabled': True, 'data': 'a',
                                'config': lambda parent: calls.append(parent)}])
    sview.set_cursor(Gtk.TreePath.new_from_indices([0]))

    sview._on_key_press(sview, SimpleNamespace(keyval=Gdk.KEY_Return))

    assert calls


def test_other_keys_are_left_to_the_default_handling():
    sview = _make_view()
    sview.set_cursor(Gtk.TreePath.new_from_indices([0]))

    handled = sview._on_key_press(sview, SimpleNamespace(keyval=Gdk.KEY_Down))

    assert handled is False


def test_column_width_accounts_for_a_configure_button_on_any_row():
    plain = SelectView(items=[{'name': 'A', 'enabled': True, 'data': 'a'}])
    with_button = SelectView(items=[{'name': 'A', 'enabled': True, 'data': 'a',
                                      'config': lambda parent: None}])

    assert with_button.namedesc_col.get_min_width() > plain.namedesc_col.get_min_width()


def test_select_item_matches_a_row_whose_enabled_state_has_changed():
    # Toggling a row's own checkbox rebuilds the model from scratch,
    # then re-selects using a snapshot taken just before the toggle -
    # matching on the whole item (including 'enabled', the very field
    # that just flipped) meant it could never find itself again.
    sview = _make_view()
    stale = dict(sview.get_all_items()[1], enabled=False)  # the real row is enabled=True

    sview.select_item(stale)

    assert sview.get_selected_item()['data'] == stale['data']


def test_select_item_moves_the_keyboard_cursor_too():
    sview = _make_view()
    target_path = Gtk.TreePath.new_from_indices([1])
    sview.set_cursor(Gtk.TreePath.new_from_indices([0]))
    target = sview.get_all_items()[1]

    sview.select_item(target)

    assert sview.get_cursor()[0] == target_path


def test_scroll_position_round_trips_through_a_scrolled_window():
    # set_model() replaces the ListStore, resetting scroll to the top -
    # a caller reselecting the same row afterwards needs its own way
    # to put the view back where it was, since GTK only scrolls as far
    # as needed to reveal that row again, not necessarily to the same
    # place.
    sview = _make_view()
    scrolled = Gtk.ScrolledWindow()
    scrolled.add(sview)
    sview.props.vadjustment.set_upper(1000)
    sview.props.vadjustment.set_value(42)

    position = sview.get_scroll_position()
    sview.props.vadjustment.set_value(0)
    sview.set_scroll_position(position)

    assert sview.props.vadjustment.get_value() == 42


def test_set_scroll_position_does_nothing_for_none():
    sview = _make_view()
    scrolled = Gtk.ScrolledWindow()
    scrolled.add(sview)
    sview.props.vadjustment.set_upper(1000)
    sview.props.vadjustment.set_value(42)

    sview.set_scroll_position(None)

    assert sview.props.vadjustment.get_value() == 42


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
