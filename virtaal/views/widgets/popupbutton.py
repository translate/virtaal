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


class PopupButton(gtk.MenuToolButton):
    """A toggle button that displays a pop-up menu when clicked."""

    # INITIALIZERS #
    def __init__(self):
        # This method is adapted from the code by Karl Ostmo from http://www.daa.com.au/pipermail/pygtk/2008-September/015918.html
        gtk.MenuToolButton.__init__(self, None, None)

        self.label = gtk.Label('')
        hbox = self.get_child()
        button, toggle_button = hbox.get_children()
        hbox.remove(button)
        toggle_button.remove(toggle_button.get_child())
        hbox = gtk.HBox()
        hbox.pack_start(self.label, False, False)
        toggle_button.add(hbox)


    # ACCESSORS #
    def _get_text(self):
        return unicode(self.label.get_text())
    def _set_text(self, value):
        self.label.set_text(value)
    text = property(_get_text, _set_text)
