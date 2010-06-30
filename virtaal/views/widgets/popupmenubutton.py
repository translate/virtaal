#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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

import gtk

# Positioning constants below:
# POS_CENTER_BELOW: Centers the pop-up window below the button (default).
# POS_CENTER_ABOVE: Centers the pop-up window above the button.
# POS_NW_SW: Positions the pop-up window so that its North West (top right)
#            corner is on the South West corner of the button.
# POS_NW_NE: Positions the pop-up window so that its North West (top right)
#            corner is on the North East corner of the button.
# POS_SW_NW: Positions the pop-up window so that its South West (top right)
#            corner is on the North West corner of the button.
POS_CENTER_BELOW, POS_CENTER_ABOVE, POS_NW_SW, POS_NW_NE, POS_SW_NW = range(5)
# XXX: Add position symbols above as needed and implementation in
#      _update_popup_geometry()

class PopupMenuButton(gtk.ToggleButton):
    """A toggle button that displays a pop-up menu when clicked."""

    # INITIALIZERS #
    def __init__(self, label=None, menu_pos=POS_SW_NW):
        gtk.ToggleButton.__init__(self, label=label)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_menu(gtk.Menu())

        self.menu_pos = menu_pos

        self.connect('toggled', self._on_toggled)


    # ACCESSORS #
    def set_menu(self, menu):
        if getattr(self, '_menu_selection_done_id', None):
            self.menu.disconnect(self._menu_selection_done_id)
        self.menu = menu
        self._menu_selection_done_id = self.menu.connect('selection-done', self._on_menu_selection_done)

    def _get_text(self):
        return unicode(self.get_label())
    def _set_text(self, value):
        self.set_label(value)
    text = property(_get_text, _set_text)


    # METHODS #
    def _calculate_popup_pos(self, menu):
        _w, menu_h = 0, 0
        menu_alloc = menu.get_allocation()
        if menu_alloc.height > 1:
            menu_h = menu_alloc.height
        else:
            _w, menu_h = menu.size_request()

        btn_window_xy = self.window.get_origin()
        btn_alloc = self.get_allocation()

        # Default values are POS_SW_NW
        x = btn_window_xy[0] + btn_alloc.x
        y = btn_window_xy[1] + btn_alloc.y - menu_h
        if self.menu_pos == POS_NW_SW:
            y = btn_window_xy[1] + btn_alloc.y + btn_alloc.height
        elif self.menu_pos == POS_NW_NE:
            x += btn_alloc.width
            y = btn_window_xy[1] + btn_alloc.y
        elif self.menu_pos == POS_CENTER_BELOW:
            x -= (menu_alloc.width - btn_alloc.width) / 2
        elif self.menu_pos == POS_CENTER_ABOVE:
            x -= (menu_alloc.width - btn_alloc.width) / 2
            y = btn_window_xy[1] - menu_alloc.height
        return (x, y, True)

    def popdown(self):
        self.menu.popdown()
        return True

    def popup(self):
        self.menu.popup(None, None, self._calculate_popup_pos, 0, 0)


    # EVENT HANDLERS #
    def _on_menu_selection_done(self, menu):
        self.set_active(False)

    def _on_toggled(self, togglebutton):
        assert self is togglebutton

        if self.get_active():
            self.popup()
        else:
            self.popdown()
