# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of virtaal.
#
# virtaal is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from bisect import bisect_left

import gobject
import gtk

class UnitModel(gtk.GenericCellRenderer):
    def __init__(self, store, editable_indices):
        gtk.GenericCellRenderer.__init__(self)
        self._store = store
        self._editable_indices = editable_indices
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
        else:
            return gobject.TYPE_BOOLEAN

    def on_get_iter(self, path):
        return path[0]

    def on_get_path(self, rowref):
        return (rowref,)

    def on_get_value(self, rowref, column):
        if column <= 1:
            unit = self._store.units[self._editable_indices[rowref]]
            if column == 0:
                return unit.getnotes() or None
            else:
                return unit
        else:
            return self._current_editable == rowref

    def on_iter_next(self, rowref):
        if rowref < len(self._editable_indices) - 1:
            return rowref + 1
        else:
            return None

    def on_iter_children(self, parent):
        if parent == None and len(self._editable_indices) > 0:
            return 0
        else:
            return None

    def on_iter_has_child(self, rowref):
        return False

    def on_iter_n_children(self, rowref):
        if rowref == None:
            return len(self._editable_indices)
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
    
    def set_editable(self, rowref):
        old_editable = self._current_editable
        self._current_editable = rowref
        self.row_changed((old_editable,), old_editable)
        self.row_changed((rowref,), rowref)

    def store_index_to_path(self, store_index):
        itr = bisect_left(self._editable_indices, store_index)
        if self._editable_indices[itr] == store_index:
            return self.get_path(itr)
        else:
            raise IndexError()

        

