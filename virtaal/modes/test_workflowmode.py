#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

from virtaal.modes.workflowmode import WorkflowMode
from virtaal.views.widgets.popupmenubutton import PopupMenuButton


def _mode(**overrides):
    mode = WorkflowMode.__new__(WorkflowMode)
    mode.filter_states = []
    mode._menuitem_states = {}
    for name, value in overrides.items():
        setattr(mode, name, value)
    return mode


def _button_with_states(*names_and_active):
    btn = PopupMenuButton()
    menu = Gtk.Menu()
    for name, active in names_and_active:
        item = Gtk.CheckMenuItem(label=name)
        item.set_active(active)
        menu.append(item)
    btn.set_menu(menu)
    return btn


# update_indices() #

def test_update_indices_does_nothing_without_a_cursor_model():
    mode = _mode(storecursor=SimpleNamespace(model=None))

    mode.update_indices()  # must not raise


def test_update_indices_shows_everything_when_no_state_is_selected():
    cursor = SimpleNamespace(model=SimpleNamespace(stats={'total': [0, 1, 2], 'extended': {}}), indices=None)
    mode = _mode(storecursor=cursor, filter_states=[])

    mode.update_indices()

    assert cursor.indices == [0, 1, 2]


def test_update_indices_shows_only_the_selected_states_units():
    cursor = SimpleNamespace(
        model=SimpleNamespace(stats={'total': [0, 1, 2, 3], 'extended': {'new': [3], 'done': [0, 1]}}),
        indices=None,
    )
    mode = _mode(storecursor=cursor, filter_states=['done', 'new'])

    mode.update_indices()

    assert cursor.indices == [0, 1, 3]


# _update_button_label() #

def test_update_button_label_prompts_when_nothing_is_selected():
    mode = _mode(btn_popup=_button_with_states(('New', False)), state_names=[('new', 'New')])

    mode._update_button_label()

    assert mode.btn_popup.get_label() == 'Select States'


def test_update_button_label_shows_all_when_every_state_is_selected():
    mode = _mode(btn_popup=_button_with_states(('New', True)), state_names=[('new', 'New')])

    mode._update_button_label()

    assert mode.btn_popup.get_label() == 'All States'


def test_update_button_label_lists_selected_states_by_name():
    mode = _mode(
        btn_popup=_button_with_states(('New', True), ('Done', False), ('Fuzzy', True)),
        state_names=[('new', 'New'), ('done', 'Done'), ('fuzzy', 'Fuzzy')],
    )

    mode._update_button_label()

    assert mode.btn_popup.get_label() == 'New, Fuzzy'


def test_update_button_label_truncates_after_three_states():
    mode = _mode(
        btn_popup=_button_with_states(('a', True), ('b', True), ('c', True), ('d', True)),
        state_names=[('a', 'a'), ('b', 'b'), ('c', 'c'), ('d', 'd'), ('e', 'e')],
    )

    mode._update_button_label()

    assert mode.btn_popup.get_label() == 'a, b, c...'


# _disable() #

def test_disable_makes_the_popup_insensitive():
    mode = _mode(btn_popup=PopupMenuButton())

    mode._disable()

    assert mode.btn_popup.get_sensitive() is False


# _on_state_menuitem_toggled() / _apply_filter_states() #

def test_on_state_menuitem_toggled_updates_filter_states_and_label(monkeypatch):
    btn = _button_with_states(('New', True), ('Done', False))
    items = btn.menu.get_children()
    idle_calls = []
    monkeypatch.setattr('virtaal.modes.workflowmode.GLib.idle_add', lambda f: idle_calls.append(f))
    mode = _mode(
        btn_popup=btn,
        state_names=[('new', 'New'), ('done', 'Done')],
        _menuitem_states={items[0]: 'new', items[1]: 'done'},
    )

    mode._on_state_menuitem_toggled(items[0])

    assert mode.filter_states == ['new']
    assert mode.btn_popup.get_label() == 'New'
    assert idle_calls == [mode._apply_filter_states]


def test_apply_filter_states_updates_indices_and_returns_false():
    calls = []
    mode = _mode()
    mode.update_indices = lambda: calls.append(True)

    result = mode._apply_filter_states()

    assert calls == [True]
    assert result is False


# unselected() #

def test_unselected_does_nothing():
    mode = _mode()

    mode.unselected()  # must not raise
