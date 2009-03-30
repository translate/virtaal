#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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
import logging

from virtaal.views.placeablesguiinfo import StringElemGUI


class TerminologyGUIInfo(StringElemGUI):
    """
    GUI info object for terminology placeables. It creates a combo box to
    choose the selected match from.
    """
    # MEMBERS #
    bg = '#eeffee'
    fg = '#006600'

    def __init__(self, elem, textbox, **kwargs):
        assert elem.__class__.__name__ == 'TerminologyPlaceable'
        super(TerminologyGUIInfo, self).__init__(elem, textbox, **kwargs)


    # METHODS #
    def create_widget(self):
        if len(self.elem.translations) > 1:
            return TerminologyCombo(self.elem)
        return None


class TerminologyCombo(gtk.ComboBox):
    """
    A combo box containing translation matches.
    """

    # INITIALIZERS #
    def __init__(self, elem):
        super(TerminologyCombo, self).__init__()
        self.anchor = None
        self.elem = elem
        self.insert_iter = None
        self.selected_string = None
        # FIXME: The following height value should be calculated from the target font.
        self.set_size_request(-1, 20)
        self.__init_combo()
        self.menu = self.menu_get_for_attach_widget()[0]
        self.menu.connect('selection-done', self._on_selection_done)

    def __init_combo(self):
        self._model = gtk.ListStore(str)
        for trans in self.elem.translations:
            self._model.append([trans])

        self.set_model(self._model)
        self._renderer = gtk.CellRendererText()
        self.pack_start(self._renderer)
        self.add_attribute(self._renderer, 'text', 0)


    # METHODS #
    def inserted(self, insert_iter, anchor):
        self.anchor = anchor
        self.insert_iter = insert_iter
        self.grab_focus()
        self.popup()

    def insert_selected(self):
        iter = self.get_active_iter()
        if iter:
            self.selected_string = self._model.get_value(iter, 0)

        if self.parent:
            self.parent.grab_focus()

        buffer = self.parent.get_buffer()
        if self.insert_iter:
            iternext = buffer.get_iter_at_offset(self.insert_iter.get_offset() + 1)
            if iternext:
                # FIXME: Not sure if the following is the best way to remove the combo box
                # from the text view.
                buffer.backspace(iternext, False, True)

        if self.selected_string:
            buffer.insert_at_cursor(self.selected_string)


    # EVENT HANDLERS #
    def _on_selection_done(self, menushell):
        self.insert_selected()
