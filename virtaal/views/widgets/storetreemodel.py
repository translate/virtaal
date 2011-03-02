#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2011 Zuza Software Foundation
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
import gobject

from virtaal.views import markup


COLUMN_NOTE, COLUMN_UNIT, COLUMN_EDITABLE = 0, 1, 2

class StoreTreeModel(gtk.GenericTreeModel):
    """Custom C{gtk.TreeModel} adapted from the old C{UnitModel} class."""

    def __init__(self, storemodel):
        gtk.GenericTreeModel.__init__(self)
        self._store = storemodel
        self._store_len = len(storemodel)
        self._current_editable = 0

    def on_get_flags(self):
        return gtk.TREE_MODEL_ITERS_PERSIST | gtk.TREE_MODEL_LIST_ONLY

    def on_get_n_columns(self):
        return 3

    def on_get_column_type(self, index):
        if index == 0:
            return gobject.TYPE_STRING
        elif index == 1:
            return gobject.TYPE_PYOBJECT
        elif index == 2:
            return gobject.TYPE_BOOLEAN

    def on_get_iter(self, path):
        return path[0]

    def on_get_path(self, rowref):
        return (rowref,)

    def on_get_value(self, rowref, column):
        if column <= 1:
            unit = self._store[rowref]
            if column == 0:
                note_text = unit.getnotes()
                if not note_text:
                    locations = unit.getlocations()
                    if locations:
                        note_text = locations[0]
                return markup.markuptext(note_text, fancyspaces=False, markupescapes=False) or None
            else:
                return unit
        else:
            return self._current_editable == rowref

    def on_iter_next(self, rowref):
        if rowref < self._store_len - 1:
            return rowref + 1
        else:
            return None

    def on_iter_children(self, parent):
        if parent == None and self._store_len > 0:
            return 0
        else:
            return None

    def on_iter_has_child(self, rowref):
        return False

    def on_iter_n_children(self, rowref):
        if rowref == None:
            return self._store_len
        else:
            return 0

    def on_iter_nth_child(self, parent, n):
        if parent == None:
            return n
        else:
            return None

    def on_iter_parent(self, child):
        return None

    # Non-model-interface methods

    def set_editable(self, new_path):
        old_path = (self._current_editable,)
        self._current_editable = new_path[0]
        self.row_changed(old_path, self.get_iter(old_path))
        self.row_changed(new_path, self.get_iter(new_path))

    def store_index_to_path(self, store_index):
        return self.on_get_path(store_index)

    def path_to_store_index(self, path):
        return path[0]
