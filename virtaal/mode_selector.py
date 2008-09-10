#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of VirTaal.
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

import gobject
import gtk
import logging

class ModeSelector(gtk.HBox):
    """A composite widget for selecting modes."""

    __gtype_name__ = "ModeSelector"

    __gsignals__ = {
        "mode-selected": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
    }

    def __init__(self, modes):
        gtk.HBox.__init__(self)

        # Add mode-selection combo box
        self.cmb_modes = gtk.combo_box_new_text()
        self.cmb_modes.connect('changed', self._on_cmbmode_change)
        self.pack_start(self.cmb_modes, expand=False)

        self.mode_names = {}
        self.mode_index = {}
        i = 0
        for mode in modes:
            self.cmb_modes.append_text(mode.user_name)
            self.mode_names[mode.user_name] = mode
            self.mode_index[mode] = i
            i += 1

    def set_mode(self, mode):
        # Remove previous mode's widgets
        if self.cmb_modes.get_active() > -1:
            for w in self.get_children():
                if w is not self.cmb_modes:
                    self.remove(w)

        # Select new mode and add its widgets
        self.cmb_modes.set_active(self.mode_index[mode])
        for w in mode.widgets:
            if w.get_parent() is None:
                self.pack_start(w, expand=False, padding=2)

        self.show_all()

    def _on_cmbmode_change(self, combo):
        self.emit('mode-selected', self.mode_names[combo.get_active_text()])
