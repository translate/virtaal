#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Workarounds for widgets that don't lay out right-to-left on their own."""

from gi.repository import Gtk


def fix_expander_direction(expander):
    """GTK 3 lays out a GtkExpander's title for right-to-left only when its
    direction changes, so one built under a right-to-left default keeps its
    title at the left with a right-pointing arrow. Change it and back."""
    if expander.get_direction() == Gtk.TextDirection.RTL:
        expander.set_direction(Gtk.TextDirection.LTR)
        expander.set_direction(Gtk.TextDirection.NONE)
