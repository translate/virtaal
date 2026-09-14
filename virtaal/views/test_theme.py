#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

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
