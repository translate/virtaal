#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Regression tests for a native segfault from popup-menu teardown racing
Python's GC (see WorkflowMode/QualityCheckMode's own _add_widgets() comment
for the full mechanism). The crash itself was only ~30% reproducible and
kills the whole test process on a hit, so it can't be tested directly -
these instead assert the fix's actual invariant: a replaced menu is
destroy()ed deterministically, not just dropped for GC to collect whenever
and however it likes."""

from unittest.mock import MagicMock

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gtk

from virtaal.views.widgets.popupmenubutton import (
    POS_CENTER_ABOVE,
    POS_CENTER_BELOW,
    POS_NE_SE,
    POS_NW_NE,
    POS_NW_SW,
    POS_SE_NE,
    POS_SW_NW,
    PopupMenuButton,
)


def test_set_menu_destroys_previous_menu():
    button = PopupMenuButton()
    old_menu = button.menu
    old_menu.destroy = MagicMock()

    button.set_menu(Gtk.Menu())

    assert old_menu.destroy.called


def test_set_menu_first_call_does_not_destroy_anything():
    # __init__ itself calls set_menu() before self.menu exists yet -
    # this must not error trying to destroy a non-existent old menu.
    PopupMenuButton()


def test_init_uses_the_given_menu_pos_in_ltr():
    button = PopupMenuButton(menu_pos=POS_NE_SE)

    assert button.menu_pos == POS_NE_SE


def test_init_remaps_menu_pos_for_rtl():
    Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
    try:
        button = PopupMenuButton(menu_pos=POS_SW_NW)
    finally:
        Gtk.Widget.set_default_direction(Gtk.TextDirection.LTR)

    assert button.menu_pos == POS_SE_NE


def test_init_falls_back_to_the_rtl_default_for_an_unmapped_pos():
    Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
    try:
        button = PopupMenuButton(menu_pos=POS_NW_NE)
    finally:
        Gtk.Widget.set_default_direction(Gtk.TextDirection.LTR)

    assert button.menu_pos == POS_SE_NE


def test_text_property_round_trips_through_the_label():
    button = PopupMenuButton()

    button.text = 'Hello'

    assert button.text == 'Hello'


def test_popdown_hides_the_menu_and_returns_true():
    button = PopupMenuButton()
    calls = []
    button.menu.popdown = lambda: calls.append(True)

    result = button.popdown()

    assert calls == [True]
    assert result is True


def _popup_call(button):
    calls = []
    button.menu.popup_at_widget = lambda *args: calls.append(args)
    button.popup()
    return calls[0]


def test_popup_default_sw_nw():
    button = PopupMenuButton(menu_pos=POS_SW_NW)

    widget, widget_anchor, menu_anchor, _event = _popup_call(button)

    assert widget is button
    assert widget_anchor == Gdk.Gravity.NORTH_WEST
    assert menu_anchor == Gdk.Gravity.SOUTH_WEST


def test_popup_nw_sw():
    button = PopupMenuButton(menu_pos=POS_NW_SW)

    _widget, widget_anchor, menu_anchor, _event = _popup_call(button)

    assert widget_anchor == Gdk.Gravity.SOUTH_WEST
    assert menu_anchor == Gdk.Gravity.NORTH_WEST


def test_popup_ne_se():
    button = PopupMenuButton(menu_pos=POS_NE_SE)

    _widget, widget_anchor, menu_anchor, _event = _popup_call(button)

    assert widget_anchor == Gdk.Gravity.SOUTH_EAST
    assert menu_anchor == Gdk.Gravity.NORTH_EAST


def test_popup_se_ne():
    button = PopupMenuButton(menu_pos=POS_SE_NE)

    _widget, widget_anchor, menu_anchor, _event = _popup_call(button)

    assert widget_anchor == Gdk.Gravity.NORTH_EAST
    assert menu_anchor == Gdk.Gravity.SOUTH_EAST


def test_popup_nw_ne():
    button = PopupMenuButton(menu_pos=POS_NW_NE)

    _widget, widget_anchor, menu_anchor, _event = _popup_call(button)

    assert widget_anchor == Gdk.Gravity.NORTH_EAST
    assert menu_anchor == Gdk.Gravity.NORTH_WEST


def test_popup_center_below():
    button = PopupMenuButton(menu_pos=POS_CENTER_BELOW)

    _widget, widget_anchor, menu_anchor, _event = _popup_call(button)

    assert widget_anchor == Gdk.Gravity.SOUTH
    assert menu_anchor == Gdk.Gravity.NORTH


def test_popup_center_above():
    button = PopupMenuButton(menu_pos=POS_CENTER_ABOVE)

    _widget, widget_anchor, menu_anchor, _event = _popup_call(button)

    assert widget_anchor == Gdk.Gravity.NORTH
    assert menu_anchor == Gdk.Gravity.SOUTH


def test_on_menu_selection_done_deactivates_the_button():
    button = PopupMenuButton()
    button.set_active(True)

    button._on_menu_selection_done(button.menu)

    assert button.get_active() is False


def test_toggled_active_opens_the_menu(monkeypatch):
    button = PopupMenuButton()
    calls = []
    monkeypatch.setattr(button, 'popup', lambda: calls.append('popup'))

    button.set_active(True)

    assert calls == ['popup']


def test_toggled_inactive_closes_the_menu(monkeypatch):
    button = PopupMenuButton()
    button.set_active(True)
    calls = []
    monkeypatch.setattr(button, 'popdown', lambda: calls.append('popdown'))

    button.set_active(False)

    assert calls == ['popdown']
