#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views import theme
from virtaal.views.theme import set_widget_fg_color


def test_set_widget_fg_color_accepts_a_hex_colour():
    # A malformed generated CSS string raises Gtk.CssProvider's own
    # GLib.GError - this is really a check that the string built here
    # is valid CSS, not just that the call completes.
    label = Gtk.Label()
    set_widget_fg_color(label, '#666')


def test_set_widget_fg_color_accepts_a_named_colour():
    label = Gtk.Label()
    set_widget_fg_color(label, 'grey')


def test_update_style_detects_a_light_theme():
    # get_background_color() always returns fully transparent in
    # current GTK3, regardless of the widget's real theme - is_inverse()
    # then always read that as "darker than the foreground", so every
    # theme-dependent colour app-wide was picked for the wrong theme
    # entirely (#3240), not just badly. gtk-application-prefer-dark-theme
    # is a process-wide GtkSettings property another test may already
    # have flipped - pin and restore it so this test doesn't depend on
    # what ran before it.
    settings = Gtk.Settings.get_default()
    original = settings.get_property('gtk-application-prefer-dark-theme')
    settings.set_property('gtk-application-prefer-dark-theme', False)
    try:
        win = Gtk.Window()
        lbl = Gtk.Label()
        win.add(lbl)
        win.show_all()

        theme.update_style(lbl)

        assert theme.INVERSE is False
    finally:
        settings.set_property('gtk-application-prefer-dark-theme', original)
