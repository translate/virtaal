#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""
PopupWidgetButton: Extends a C{gtk.ToggleButton} to show a given widget in a
pop-up window.
"""

import gtk
from gobject import SIGNAL_RUN_FIRST

# XXX: Kudo's to Toms Bauģis <toms.baugis at gmail.com> who wrote the
#      ActivityEntry widget for the hamster-applet project. A lot of this
#      class's signal handling is based on his example.

# Positioning constants below:
# POS_CENTER_BELOW: Centers the pop-up window below the button (default).
# POS_CENTER_ABOVE: Centers the pop-up window above the button.
# POS_NW_SW: Positions the pop-up window so that its North West (top right)
#            corner is on the South West corner of the button.
# POS_NW_NE: Positions the pop-up window so that its North West (top right)
#            corner is on the North East corner of the button.
# POS_SE_NE: Positions the pop-up window so that its South East (top right)
#            corner is on the North East corner of the button.
POS_CENTER_BELOW, POS_CENTER_ABOVE, POS_NW_SW, POS_NW_NE, POS_SE_NE = range(5)
# XXX: Add position symbols above as needed and implementation in
#      _update_popup_geometry()

class PopupWidgetButton(gtk.ToggleButton):
    """Extends a C{gtk.ToggleButton} to show a given widget in a pop-up window."""
    __gtype_name__ = 'PopupWidgetButton'
    __gsignals__ = {
        'shown':  (SIGNAL_RUN_FIRST, None, ()),
        'hidden': (SIGNAL_RUN_FIRST, None, ()),
    }

    # INITIALIZERS #
    def __init__(self, widget, label='Pop-up', popup_pos=POS_NW_SW):
        super(PopupWidgetButton, self).__init__(label=label)
        self.connect('focus-out-event', self._on_focus_out_event)
        self.connect('key-press-event', self._on_key_press_event)
        self.connect('toggled', self._on_toggled)

        self.popup_pos = popup_pos
        self._parent_button_press_id = None
        self._update_popup_geometry_func = None

        # Create pop-up window
        self.popup = gtk.Window(type=gtk.WINDOW_POPUP)
        self.popup.add(widget)
        self.popup.show_all()
        self.popup.hide()


    # ACCESSORS #
    def _get_is_popup_visible(self):
        return self.popup.props.visible
    is_popup_visible = property(_get_is_popup_visible)

    def set_update_popup_geometry_func(self, func):
        self._update_popup_geometry_func = func

    # METHODS #
    def calculate_popup_xy(self, popup_alloc, btn_alloc, btn_window_xy):
        # Default values are POS_NW_SW
        x = btn_window_xy[0] + btn_alloc.x
        y = btn_window_xy[1] + btn_alloc.y + btn_alloc.height
        width, height = self.popup.get_child_requisition()

        if self.popup_pos == POS_NW_NE:
            x += btn_alloc.width
            y = btn_window_xy[1] + btn_alloc.y
        elif self.popup_pos == POS_SE_NE:
            x -= (popup_alloc.width - btn_alloc.width)
            y = btn_window_xy[1] - popup_alloc.height
        elif self.popup_pos == POS_CENTER_BELOW:
            x -= (popup_alloc.width - btn_alloc.width) / 2
        elif self.popup_pos == POS_CENTER_ABOVE:
            x -= (popup_alloc.width - btn_alloc.width) / 2
            y = btn_window_xy[1] - popup_alloc.height

        return x, y

    def hide_popup(self):
        self.set_active(False)

    def show_popup(self):
        self.set_active(True)

    def _do_hide_popup(self):
        if self._parent_button_press_id and self.get_toplevel().handler_is_connected(self._parent_button_press_id):
            self.get_toplevel().disconnect(self._parent_button_press_id)
            self._parent_button_press_id = None
        self.popup.hide()
        self.emit('hidden')

    def _do_show_popup(self):
        if not self._parent_button_press_id and self.get_toplevel():
            self._parent_button_press_id = self.get_toplevel().connect('button-press-event', self._on_focus_out_event)
        self.popup.present()
        self._update_popup_geometry()
        self.emit('shown')

    def _update_popup_geometry(self):
        self.popup.set_size_request(-1, -1)
        width, height = self.popup.get_child_requisition()
        self.popup.set_size_request(width, height)

        x, y = -1, -1
        width, height = self.popup.get_child_requisition()
        popup_alloc = self.popup.get_allocation()
        btn_window_xy = self.window.get_origin()
        btn_alloc = self.get_allocation()

        if callable(self._update_popup_geometry_func):
            x, y, new_width, new_height = self._update_popup_geometry_func(
                self.popup, popup_alloc, btn_alloc, btn_window_xy,
                (x, y, width, height)
            )
            if new_width != width or new_height != height:
                width, height = new_width, new_height
                self.popup.set_size_request(width, height)

        popup_alloc.width, popup_alloc.height = width, height
        x, y = self.calculate_popup_xy(popup_alloc, btn_alloc, btn_window_xy)

        self.popup.reshow_with_initial_size()
        self.popup.move(x, y)


    # EVENT HANDLERS #
    def _on_focus_out_event(self, window, event):
        self.hide_popup()

    def _on_key_press_event(self, window, event):
        if event.keyval == gtk.keysyms.Escape and self.popup.props.visible:
            self.hide_popup()
            return True
        return False

    def _on_toggled(self, button):
        if button.get_active():
            self._do_show_popup()
        else:
            self._do_hide_popup()


if __name__ == '__main__':
    btn = PopupWidgetButton(label='TestMe', widget=gtk.Button('Click me'))

    hb = gtk.HBox()
    hb.pack_start(gtk.Button('Left'),  expand=False, fill=False)
    hb.pack_start(btn,                 expand=False, fill=False)
    hb.pack_start(gtk.Button('Right'), expand=False, fill=False)
    vb = gtk.VBox()
    vb.pack_start(hb, expand=False, fill=False)

    from testwindow import Window
    wnd = Window(size=(400, 300), title='Pop-up Window Button Test', widget=vb)
    wnd.show()
