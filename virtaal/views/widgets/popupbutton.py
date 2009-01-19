#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
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


class PopupButton(gtk.ToggleButton):
    """A toggle button that displays a pop-up menu when clicked."""

    # INITIALIZERS #
    def __init__(self):
        gtk.ToggleButton.__init__(self)
        self.set_relief(gtk.RELIEF_NONE)

        self.set_menu(gtk.Menu())

        self.connect('toggled', self._on_toggled)
        self.connect('focus-out-event', lambda *args: self.popdown())


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
        alloc = self.get_allocation()
        return (alloc.x, alloc.y, True)

    def popdown(self):
        self.menu.popdown()
        return True

    def popup(self):
        self.menu.show_all()
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
