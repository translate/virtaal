#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk, Pango

from virtaal.views.rendering import set_widget_font


def test_set_widget_font_accepts_a_family_and_point_size():
    # font: <Pango description> is accepted by Gtk.CssProvider but
    # rejected as "not a number" for some descriptions (e.g. a family
    # followed by a bare size, "Monospace 10") - family/size as their
    # own CSS properties avoids relying on that shorthand at all.
    label = Gtk.Label()
    set_widget_font(label, Pango.FontDescription('Monospace 10'))


def test_set_widget_font_accepts_an_absolute_size():
    label = Gtk.Label()
    desc = Pango.FontDescription('Sans 12px')
    assert desc.get_size_is_absolute()
    set_widget_font(label, desc)
