#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gdk


def is_wayland():
    display = Gdk.Display.get_default()
    return display is not None and display.__gtype__.name == 'GdkWaylandDisplay'


def set_popup_parent(popup, parent):
    """On Wayland, a popup window without a parent opens as a window of its
        own: it can't be placed, and it takes the focus from C{parent}."""
    if is_wayland():
        popup.set_transient_for(parent)
