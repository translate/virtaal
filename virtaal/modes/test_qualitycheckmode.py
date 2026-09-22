#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

from virtaal.modes.qualitycheckmode import QualityCheckMode
from virtaal.views.widgets.popupmenubutton import PopupMenuButton


def _mode(**overrides):
    mode = QualityCheckMode.__new__(QualityCheckMode)
    mode.filter_checks = []
    mode._menuitem_checks = {}
    for name, value in overrides.items():
        setattr(mode, name, value)
    return mode


# _prepare_stats() #

def test_prepare_stats_names_every_non_meta_check_with_failures():
    mode = _mode(
        store_controller=SimpleNamespace(
            update_store_checks=lambda checker: None,
            get_store_checks=lambda: {
                'total': [0, 1, 2],
                'translated': [0],
                'untranslated': [],
                'extended': [],
                'brackets': [1],
                'printf': [],
            },
            cursor=SimpleNamespace(),
        ),
        main_controller=SimpleNamespace(
            checks_controller=SimpleNamespace(
                get_checker=lambda: 'standard',
                get_check_name=lambda check: check.upper(),
            )
        ),
    )

    mode._prepare_stats()

    assert mode.checks_names == {'brackets': 'BRACKETS'}


def test_prepare_stats_drops_a_filter_check_that_disappeared():
    mode = _mode(
        filter_checks=['brackets', 'printf'],
        store_controller=SimpleNamespace(
            update_store_checks=lambda checker: None,
            get_store_checks=lambda: {'total': [], 'brackets': [1]},
            cursor=SimpleNamespace(),
        ),
        main_controller=SimpleNamespace(
            checks_controller=SimpleNamespace(get_checker=lambda: None, get_check_name=lambda c: c)
        ),
    )

    mode._prepare_stats()

    assert mode.filter_checks == ['brackets']


# update_indices() #

def test_update_indices_does_nothing_without_a_cursor_model():
    mode = _mode(storecursor=SimpleNamespace(model=None))

    mode.update_indices()  # must not raise


def test_update_indices_shows_everything_when_no_check_is_selected():
    cursor = SimpleNamespace(model=[object(), object(), object()], indices=None)
    mode = _mode(storecursor=cursor, filter_checks=[], stats={})

    mode.update_indices()

    assert cursor.indices == [0, 1, 2]


def test_update_indices_shows_only_the_selected_checks_units():
    cursor = SimpleNamespace(model=[object()] * 5, indices=None)
    mode = _mode(
        storecursor=cursor,
        filter_checks=['printf', 'brackets'],
        stats={'printf': [3], 'brackets': [0, 1]},
    )

    mode.update_indices()

    assert cursor.indices == [0, 1, 3]


# _update_button_label() #

def _button_with_checks(*names_and_active):
    btn = PopupMenuButton()
    menu = Gtk.Menu()
    for name, active in names_and_active:
        item = Gtk.CheckMenuItem(label=name)
        item.set_active(active)
        menu.append(item)
    btn.set_menu(menu)
    return btn


def test_update_button_label_prompts_when_nothing_is_selected():
    mode = _mode(btn_popup=_button_with_checks(('brackets', False)), checks_names={'brackets': 'x'})

    mode._update_button_label()

    assert mode.btn_popup.get_label() == 'Select Checks'


def test_update_button_label_shows_all_when_everything_is_selected():
    mode = _mode(
        btn_popup=_button_with_checks(('brackets', True)),
        checks_names={'brackets': 'x'},
    )

    mode._update_button_label()

    assert mode.btn_popup.get_label() == 'All Checks'


def test_update_button_label_lists_selected_checks_by_name():
    mode = _mode(
        btn_popup=_button_with_checks(('brackets', True), ('printf', False), ('unchanged', True)),
        checks_names={'brackets': 'x', 'printf': 'y', 'unchanged': 'z'},
    )

    mode._update_button_label()

    assert mode.btn_popup.get_label() == 'brackets, unchanged'


def test_update_button_label_truncates_after_three_checks():
    mode = _mode(
        btn_popup=_button_with_checks(('a', True), ('b', True), ('c', True), ('d', True)),
        checks_names={'a': 1, 'b': 1, 'c': 1, 'd': 1, 'e': 1},
    )

    mode._update_button_label()

    assert mode.btn_popup.get_label() == 'a, b, c...'


# _create_menu_entries() #

def test_create_menu_entries_builds_one_item_per_named_check():
    mode = _mode(
        checks_names={'brackets': 'Brackets'},
        filter_checks=['brackets'],
        stats={'brackets': [0, 1]},
    )
    menu = Gtk.Menu()

    mode._create_menu_entries(menu)

    items = menu.get_children()
    assert len(items) == 1
    assert items[0].get_label() == 'Brackets (2)'
    assert items[0].get_active() is True
    assert mode._menuitem_checks[items[0]][0] == 'brackets'


def test_create_menu_entries_clears_previous_entries_first():
    mode = _mode(checks_names={}, filter_checks=[], stats={})
    menu = Gtk.Menu()
    stale_item = Gtk.CheckMenuItem(label='stale')
    menu.append(stale_item)
    signal_id = stale_item.connect('toggled', lambda w: None)
    mode._menuitem_checks = {stale_item: ('stale', signal_id)}

    mode._create_menu_entries(menu)

    assert menu.get_children() == []
    assert mode._menuitem_checks == {}


# _on_check_menuitem_toggled() #

def test_on_check_menuitem_toggled_rebuilds_filter_checks_from_active_items():
    btn = _button_with_checks(('brackets', True), ('printf', False))
    items = btn.menu.get_children()
    mode = _mode(
        btn_popup=btn,
        checks_names={'brackets': 'x', 'printf': 'y'},
        storecursor=SimpleNamespace(model=None),
        _menuitem_checks={items[0]: ('brackets', 0), items[1]: ('printf', 0)},
    )

    mode._on_check_menuitem_toggled(items[0])

    assert mode.filter_checks == ['brackets']


# unselected() #

def test_unselected_disconnects_the_tracked_signals():
    disconnected = []
    mode = _mode(
        _checker_set_id=1,
        _store_saved_id=2,
        main_controller=SimpleNamespace(
            checks_controller=SimpleNamespace(disconnect=lambda i: disconnected.append(('checker', i)))
        ),
        store_controller=SimpleNamespace(disconnect=lambda i: disconnected.append(('store', i))),
    )

    mode.unselected()

    assert disconnected == [('checker', 1), ('store', 2)]
    assert mode._checker_set_id is None


def test_unselected_is_a_noop_without_a_tracked_signal():
    mode = _mode(_checker_set_id=None)

    mode.unselected()  # must not raise
