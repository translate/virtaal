#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gdk, Gtk

from virtaal.views.widgets.popupwidgetbutton import (
    POS_CENTER_ABOVE,
    POS_CENTER_BELOW,
    POS_NE_SE,
    POS_NW_NE,
    POS_NW_SW,
    POS_SE_NE,
    POS_SW_NW,
    PopupWidgetButton,
)


def _make_button(**kwargs):
    window = Gtk.Window()
    btn = PopupWidgetButton(widget=Gtk.Label(label='content'), **kwargs)
    window.add(btn)
    window.show_all()
    return window, btn


def test_init_uses_the_given_popup_pos_in_ltr():
    _, btn = _make_button(popup_pos=POS_NE_SE)

    assert btn.popup_pos == POS_NE_SE


def test_init_remaps_popup_pos_for_rtl():
    Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
    try:
        _, btn = _make_button(popup_pos=POS_NW_SW)
    finally:
        Gtk.Widget.set_default_direction(Gtk.TextDirection.LTR)

    assert btn.popup_pos == POS_NE_SE


def test_init_falls_back_to_the_rtl_default_for_an_unmapped_pos():
    Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
    try:
        _, btn = _make_button(popup_pos=POS_NW_NE)
    finally:
        Gtk.Widget.set_default_direction(Gtk.TextDirection.LTR)

    assert btn.popup_pos == POS_NE_SE


def test_focus_out_event_hides_the_popup_by_default():
    _, btn = _make_button()
    btn.show_popup()
    assert btn.is_popup_visible

    btn.emit('focus-out-event', Gdk.Event.new(Gdk.EventType.FOCUS_CHANGE))

    assert not btn.is_popup_visible


def test_sticky_button_ignores_focus_out_event():
    _, btn = _make_button(sticky=True)
    btn.show_popup()

    btn.emit('focus-out-event', Gdk.Event.new(Gdk.EventType.FOCUS_CHANGE))

    assert btn.is_popup_visible


def test_main_window_focus_out_also_hides_the_popup():
    main_window = Gtk.Window()
    _, btn = _make_button(main_window=main_window)
    btn.show_popup()

    main_window.emit('focus-out-event', Gdk.Event.new(Gdk.EventType.FOCUS_CHANGE))

    assert not btn.is_popup_visible


def _key_event(keyval):
    event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    event.key.keyval = keyval
    return event


def test_escape_key_hides_a_visible_popup_and_consumes_the_event():
    _, btn = _make_button()
    btn.show_popup()

    handled = btn._on_key_press_event(btn, _key_event(Gdk.KEY_Escape))

    assert handled is True
    assert not btn.is_popup_visible


def test_escape_key_is_ignored_when_the_popup_is_already_hidden():
    _, btn = _make_button()

    handled = btn._on_key_press_event(btn, _key_event(Gdk.KEY_Escape))

    assert handled is False


def test_other_keys_are_ignored():
    _, btn = _make_button()
    btn.show_popup()

    handled = btn._on_key_press_event(btn, _key_event(Gdk.KEY_a))

    assert handled is False
    assert btn.is_popup_visible


def test_toggled_true_shows_the_popup():
    _, btn = _make_button()

    btn.set_active(True)

    assert btn.is_popup_visible


def test_toggled_false_hides_the_popup():
    _, btn = _make_button()
    btn.set_active(True)

    btn.set_active(False)

    assert not btn.is_popup_visible


def test_set_update_popup_geometry_func_stores_the_function():
    _, btn = _make_button()
    func = lambda *a: None

    btn.set_update_popup_geometry_func(func)

    assert btn._update_popup_geometry_func is func


def test_hide_popup_deactivates_the_button():
    _, btn = _make_button()
    btn.set_active(True)

    btn.hide_popup()

    assert not btn.get_active()


def test_show_popup_activates_the_button():
    _, btn = _make_button()

    btn.show_popup()

    assert btn.get_active()


def test_do_show_popup_connects_the_toplevel_button_press_handler():
    _, btn = _make_button()

    btn._do_show_popup()

    assert btn._parent_button_press_id is not None
    assert btn.popup.props.visible


def test_do_show_popup_does_not_reconnect_an_already_connected_handler():
    _, btn = _make_button()
    btn._do_show_popup()
    first_id = btn._parent_button_press_id

    btn._do_show_popup()

    assert btn._parent_button_press_id == first_id


def test_do_hide_popup_disconnects_the_parent_button_press_handler():
    _, btn = _make_button()
    btn._do_show_popup()

    btn._do_hide_popup()

    assert btn._parent_button_press_id is None
    assert not btn.popup.props.visible


def test_do_hide_popup_is_a_noop_when_nothing_was_connected():
    _, btn = _make_button()

    btn._do_hide_popup()  # must not raise

    assert not btn.popup.props.visible


def test_do_hide_popup_emits_hidden(monkeypatch):
    _, btn = _make_button()
    calls = []
    btn.connect('hidden', lambda b: calls.append(True))

    btn._do_hide_popup()

    assert calls == [True]


def test_do_show_popup_emits_shown():
    _, btn = _make_button()
    calls = []
    btn.connect('shown', lambda b: calls.append(True))

    btn._do_show_popup()

    assert calls == [True]


def test_on_expose_updates_the_popup_geometry(monkeypatch):
    _, btn = _make_button()
    calls = []
    monkeypatch.setattr(btn, '_update_popup_geometry', lambda: calls.append(True))

    btn._on_expose(btn, None)

    assert calls == [True]


def test_update_popup_geometry_uses_the_custom_geometry_func_when_set():
    _, btn = _make_button()
    calls = []

    def geometry_func(popup, popup_alloc, btn_alloc, btn_window_xy, defaults):
        calls.append((popup_alloc, btn_alloc, btn_window_xy, defaults))
        x, y, width, height = defaults
        return x, y, width + 10, height + 10

    btn.set_update_popup_geometry_func(geometry_func)

    btn._update_popup_geometry()

    assert len(calls) == 1


def _rect(x=0, y=0, width=0, height=0):
    return SimpleNamespace(x=x, y=y, width=width, height=height)


def _fake_button(popup_pos):
    return SimpleNamespace(popup_pos=popup_pos)


POPUP_ALLOC = _rect(width=50, height=20)
BTN_ALLOC = _rect(x=5, y=0, width=30, height=10)
BTN_WINDOW_XY = _rect(x=100, y=200)


def test_calculate_popup_xy_defaults_to_below_and_aligned_left():
    fake_self = _fake_button(POS_NW_SW)

    result = PopupWidgetButton.calculate_popup_xy(fake_self, POPUP_ALLOC, BTN_ALLOC, BTN_WINDOW_XY)

    assert result == (105, 210)


def test_calculate_popup_xy_ne_se_aligns_right_edges_below():
    fake_self = _fake_button(POS_NE_SE)

    result = PopupWidgetButton.calculate_popup_xy(fake_self, POPUP_ALLOC, BTN_ALLOC, BTN_WINDOW_XY)

    assert result == (85, 210)


def test_calculate_popup_xy_nw_ne_positions_to_the_right():
    fake_self = _fake_button(POS_NW_NE)

    result = PopupWidgetButton.calculate_popup_xy(fake_self, POPUP_ALLOC, BTN_ALLOC, BTN_WINDOW_XY)

    assert result == (135, 200)


def test_calculate_popup_xy_se_ne_positions_to_the_right_above():
    fake_self = _fake_button(POS_SE_NE)

    result = PopupWidgetButton.calculate_popup_xy(fake_self, POPUP_ALLOC, BTN_ALLOC, BTN_WINDOW_XY)

    assert result == (85, 180)


def test_calculate_popup_xy_sw_nw_positions_above_aligned_left():
    fake_self = _fake_button(POS_SW_NW)

    result = PopupWidgetButton.calculate_popup_xy(fake_self, POPUP_ALLOC, BTN_ALLOC, BTN_WINDOW_XY)

    assert result == (105, 180)


def test_calculate_popup_xy_center_below_centers_horizontally():
    fake_self = _fake_button(POS_CENTER_BELOW)

    result = PopupWidgetButton.calculate_popup_xy(fake_self, POPUP_ALLOC, BTN_ALLOC, BTN_WINDOW_XY)

    assert result == (95, 210)


def test_calculate_popup_xy_center_above_centers_horizontally_and_flips_vertically():
    fake_self = _fake_button(POS_CENTER_ABOVE)

    result = PopupWidgetButton.calculate_popup_xy(fake_self, POPUP_ALLOC, BTN_ALLOC, BTN_WINDOW_XY)

    assert result == (95, 180)
