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
    mode._stats_changed_id = None
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


def test_update_indices_is_empty_when_the_selected_states_have_no_units():
    cursor = SimpleNamespace(
        model=SimpleNamespace(stats={'total': [0, 1], 'extended': {'new': [], 'done': [0, 1]}}),
        indices=None,
    )
    mode = _mode(storecursor=cursor, filter_states=['new'])

    mode.update_indices()

    assert cursor.indices == []


# selected() #

_FORMAT_STATES = {'gone': (-100, 0), 'new': (0, 30), 'fuzzy': (30, 100), 'done': (100, 127)}


class _Model:
    def __init__(self, stats, states=_FORMAT_STATES):
        self.stats = stats
        unit_class = type('Unit', (), {'STATE': states})
        self.units = [unit_class() for _index in stats['total']]

    def __len__(self):
        return len(self.units)

    def __getitem__(self, index):
        return self.units[index]


def _controller(stats, states=_FORMAT_STATES):
    cursor = SimpleNamespace(model=_Model(stats, states), indices=None)
    names = {'gone': 'Obsolete', 'new': 'New', 'fuzzy': 'Needs work', 'done': 'Done'}
    return SimpleNamespace(
        main_controller=SimpleNamespace(
            store_controller=SimpleNamespace(cursor=cursor, connect=lambda signal, handler: 7, disconnect=lambda i: None),
            unit_controller=SimpleNamespace(get_unit_state_names=lambda: names),
        ),
        view=SimpleNamespace(mode_box=Gtk.Grid()),
    )


def _menu(mode):
    return [(item.get_label(), item.get_active(), item.get_sensitive()) for item in mode.btn_popup.menu]


def test_selected_lists_the_formats_states_and_greys_out_those_without_units():
    mode = _mode(controller=_controller({'total': [0, 1], 'extended': {'done': [0], 'new': [1]}}))

    mode.selected()

    assert _menu(mode) == [('Done', False, True), ('Needs work', False, False), ('New', False, True)]


def test_selected_lists_the_states_units_are_in_for_a_format_without_states():
    mode = _mode(controller=_controller({'total': [0], 'extended': {'done': [0]}}, states={}))

    mode.selected()

    assert mode.state_names == [('done', 'Done')]


def test_selected_ticks_the_menu_items_of_the_states_still_filtered():
    mode = _mode(
        filter_states=['fuzzy'],
        controller=_controller({'total': [0, 1], 'extended': {'fuzzy': [1], 'done': [0]}}),
    )

    mode.selected()

    assert ('Needs work', True, True) in _menu(mode)
    assert mode.btn_popup.get_label() == 'Needs work'
    assert mode.storecursor.indices == [1]


def test_selected_drops_a_ticked_state_no_unit_is_in():
    # Reselecting the mode, or opening a file while it is selected.
    mode = _mode(
        filter_states=['fuzzy'],
        controller=_controller({'total': [0, 1], 'extended': {'done': [0, 1]}}),
    )

    mode.selected()

    assert mode.filter_states == []
    assert mode.storecursor.indices == [0, 1]


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
        storecursor=SimpleNamespace(model=None),
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


# _on_stats_changed() #

def test_a_ticked_state_whose_units_all_move_on_stays_until_unticked(monkeypatch):
    monkeypatch.setattr('virtaal.modes.workflowmode.GLib.idle_add', lambda f: None)
    controller = _controller({'total': [0, 1], 'extended': {'fuzzy': [1], 'done': [0]}})
    mode = _mode(controller=controller)
    mode.selected()
    fuzzy = [item for item in mode.btn_popup.menu if item.get_label() == 'Needs work'][0]
    fuzzy.set_active(True)
    mode.update_indices()
    # Unit 1 is marked translated.
    controller.main_controller.store_controller.cursor.model.stats['extended'] = {'done': [0, 1]}

    mode._on_stats_changed(None)

    assert ('Needs work', True, True) in _menu(mode)
    assert mode.storecursor.indices == [1]

    fuzzy.set_active(False)

    assert ('Needs work', False, False) in _menu(mode)


# unselected() #

def test_unselected_disconnects_from_stats_changed():
    disconnected = []
    mode = _mode(
        _stats_changed_id=7,
        controller=SimpleNamespace(main_controller=SimpleNamespace(
            store_controller=SimpleNamespace(disconnect=disconnected.append))),
    )

    mode.unselected()

    assert disconnected == [7]
    assert mode._stats_changed_id is None


def test_unselected_without_a_connection_does_nothing():
    mode = _mode()

    mode.unselected()  # must not raise
