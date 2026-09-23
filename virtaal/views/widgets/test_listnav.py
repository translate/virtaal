#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gdk, Gtk

from virtaal.views.widgets.listnav import ListNavigator


def _make_model(names):
    lst = Gtk.ListStore(str, object)
    for name in names:
        lst.append([name, SimpleNamespace(name=name)])
    return lst


def _make_navigator(names, **kwargs):
    navigator = ListNavigator()
    navigator.set_model(_make_model(names), **kwargs)
    return navigator


def _selected_name(navigator):
    model, itr = navigator.tvw_items.get_selection().get_selected()
    return model.get_value(itr, ListNavigator.COL_DISPLAY)


def _key_event(keyval, state=Gdk.ModifierType(0)):
    event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    event.key.keyval = keyval
    event.key.state = state
    key_event = event.key
    key_event._owning_event = event  # keep the union's backing memory alive
    return key_event


def test_set_model_rejects_a_non_string_display_column():
    navigator = ListNavigator()
    model = Gtk.ListStore(object, object)

    with pytest.raises(ValueError):
        navigator.set_model(model)


def test_set_model_rejects_a_non_object_value_column():
    navigator = ListNavigator()
    model = Gtk.ListStore(str, str)

    with pytest.raises(ValueError):
        navigator.set_model(model)


def test_set_model_selects_the_first_row_by_default():
    navigator = _make_navigator(['one', 'two', 'three'])

    assert _selected_name(navigator) == 'one'


def test_set_model_can_skip_selecting_anything():
    navigator = ListNavigator()

    navigator.set_model(_make_model(['one', 'two']), select_first=False)

    model, itr = navigator.tvw_items.get_selection().get_selected()
    assert itr is None


def test_set_model_selects_by_name_overriding_select_first():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='two')

    assert _selected_name(navigator) == 'two'
    assert navigator.btn_popup.get_label() == 'two'


def test_move_state_moves_forward_within_bounds():
    navigator = _make_navigator(['one', 'two', 'three'])

    navigator.move_state(1)

    assert _selected_name(navigator) == 'two'


def test_move_state_clamps_at_the_end():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='three')

    navigator.move_state(1)

    assert _selected_name(navigator) == 'three'


def test_move_state_clamps_at_the_start():
    navigator = _make_navigator(['one', 'two', 'three'])

    navigator.move_state(-1)

    assert _selected_name(navigator) == 'one'


def test_move_state_refuses_to_move_onto_an_unselectable_row():
    navigator = _make_navigator(['one', 'skip', 'three'], unselectable=['skip'])

    navigator.move_state(1)

    assert _selected_name(navigator) == 'one'


def test_move_state_can_move_past_an_unselectable_row_once_already_there(monkeypatch):
    # move_state()'s unselectable guard only ever blocks stepping ONTO an
    # unselectable row - it doesn't stop the caller stepping further once
    # already there (e.g. via select_by_name()).
    navigator = _make_navigator(['one', 'skip', 'three'], unselectable=['skip'])
    navigator.tvw_items.set_cursor(1)

    navigator.move_state(1)

    assert _selected_name(navigator) == 'three'


def test_select_by_name_selects_the_matching_row():
    navigator = _make_navigator(['one', 'two', 'three'])

    navigator.select_by_name('two')

    assert _selected_name(navigator) == 'two'


def test_select_by_name_does_nothing_for_an_unknown_name():
    navigator = _make_navigator(['one', 'two'])

    navigator.select_by_name('missing')

    assert _selected_name(navigator) == 'one'


def test_select_by_object_selects_the_matching_row():
    navigator = ListNavigator()
    model = _make_model(['one', 'two'])
    navigator.set_model(model)
    target = model[1][ListNavigator.COL_VALUE]

    navigator.select_by_object(target)

    assert _selected_name(navigator) == 'two'


def test_set_tooltips_text_sets_all_three_tooltips():
    navigator = ListNavigator()

    navigator.set_tooltips_text('back', 'default', 'forward')

    assert navigator.btn_back.get_tooltip_text() == 'back'
    assert navigator.get_tooltip_text() == 'default'
    assert navigator.btn_forward.get_tooltip_text() == 'forward'


def test_set_parent_window_sets_the_popups_transient_parent():
    navigator = ListNavigator()
    window = Gtk.Window()

    navigator.set_parent_window(window)

    assert navigator.btn_popup.popup.get_transient_for() is window


def test_back_clicked_emits_signal_and_moves_backward():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='two')
    calls = []
    navigator.connect('back-clicked', lambda n: calls.append(True))

    navigator.btn_back.emit('clicked')

    assert calls == [True]
    assert _selected_name(navigator) == 'one'


def test_forward_clicked_emits_signal_and_moves_forward():
    navigator = _make_navigator(['one', 'two', 'three'])
    calls = []
    navigator.connect('forward-clicked', lambda n: calls.append(True))

    navigator.btn_forward.emit('clicked')

    assert calls == [True]
    assert _selected_name(navigator) == 'two'


def test_popup_key_press_up_moves_backward_when_popup_visible():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='two')
    navigator.btn_popup.popup.show()

    handled = navigator._on_popup_key_press_event(navigator.btn_popup, _key_event(Gdk.KEY_Up))

    assert handled is True
    assert _selected_name(navigator) == 'one'


def test_popup_key_press_down_moves_forward_when_popup_visible():
    navigator = _make_navigator(['one', 'two', 'three'])
    navigator.btn_popup.popup.show()

    handled = navigator._on_popup_key_press_event(navigator.btn_popup, _key_event(Gdk.KEY_Down))

    assert handled is True
    assert _selected_name(navigator) == 'two'


def test_popup_key_press_up_ignored_when_popup_not_visible():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='two')
    navigator.btn_popup.popup.hide()

    handled = navigator._on_popup_key_press_event(navigator.btn_popup, _key_event(Gdk.KEY_Up))

    assert handled is False
    assert _selected_name(navigator) == 'two'


def test_popup_key_press_ignores_up_with_a_modifier_held():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='two')
    navigator.btn_popup.popup.show()

    handled = navigator._on_popup_key_press_event(
        navigator.btn_popup, _key_event(Gdk.KEY_Up, Gdk.ModifierType.CONTROL_MASK))

    assert handled is False
    assert _selected_name(navigator) == 'two'


def test_popup_key_press_ignores_other_keys():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='two')
    navigator.btn_popup.popup.show()

    handled = navigator._on_popup_key_press_event(navigator.btn_popup, _key_event(Gdk.KEY_a))

    assert handled is False


def test_selection_changed_updates_the_popup_label():
    navigator = _make_navigator(['one', 'two', 'three'])

    navigator.select_by_name('two')

    assert navigator.btn_popup.get_label() == 'two'


def test_selection_changed_disables_back_button_on_the_first_row():
    navigator = _make_navigator(['one', 'two', 'three'])

    assert not navigator.btn_back.get_sensitive()
    assert navigator.btn_forward.get_sensitive()


def test_selection_changed_disables_forward_button_on_the_last_row():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='three')

    assert navigator.btn_back.get_sensitive()
    assert not navigator.btn_forward.get_sensitive()


def test_selection_changed_enables_both_buttons_in_the_middle():
    navigator = _make_navigator(['one', 'two', 'three'], select_name='two')

    assert navigator.btn_back.get_sensitive()
    assert navigator.btn_forward.get_sensitive()


def test_selection_changed_skips_over_an_unselectable_row_when_emitting():
    navigator = ListNavigator()
    model = _make_model(['one', 'skip', 'three'])
    navigator.set_model(model, unselectable=['skip'])

    navigator.tvw_items.get_selection().select_iter(model[1].iter)

    assert _selected_name(navigator) == 'three'


def test_selection_changed_emits_selection_changed_with_the_selected_value():
    navigator = ListNavigator()
    model = _make_model(['one', 'two'])
    navigator.set_model(model)
    calls = []
    navigator.connect('selection-changed', lambda n, value: calls.append(value))

    navigator.tvw_items.get_selection().select_iter(model[1].iter)

    assert calls == [model[1][ListNavigator.COL_VALUE]]


def test_select_by_name_does_not_emit_selection_changed():
    # unitview.py's own caller relies on this: "Update it without
    # emitting any signals or recreating anything."
    navigator = _make_navigator(['one', 'two'])
    calls = []
    navigator.connect('selection-changed', lambda n, value: calls.append(value))

    navigator.select_by_name('two')

    assert calls == []
