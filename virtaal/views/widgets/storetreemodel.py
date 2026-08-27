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

from gi.repository import GObject
from gi.repository import Gtk

from virtaal.views import markup

COLUMN_NOTE, COLUMN_UNIT, COLUMN_EDITABLE = 0, 1, 2


class StoreTreeModel(GObject.GObject, Gtk.TreeModel):
    """Custom C{Gtk.TreeModel} adapted from the old C{UnitModel} class.

    This implements Gtk.TreeModel's do_* virtual methods directly. It used
    to be built on pygtkcompat.generictreemodel.GenericTreeModel's on_*
    convenience wrappers, but that module was removed from PyGObject
    (deprecated November 2023, removed 2024/2025) and relied on ctypes to
    poke a Python object pointer into a Gtk.TreeIter's C struct - exactly
    the kind of thing not worth resurrecting. This model is flat
    (LIST_ONLY, no real tree hierarchy), so each row is just addressed by
    its integer index, stored directly in Gtk.TreeIter.user_data.
    """

    def __init__(self, storemodel):
        super(StoreTreeModel, self).__init__()
        self._store = storemodel
        self._store_len = len(storemodel)
        self._current_editable = 0

    def do_get_flags(self):
        return Gtk.TreeModelFlags.ITERS_PERSIST | Gtk.TreeModelFlags.LIST_ONLY

    def do_get_n_columns(self):
        return 3

    def do_get_column_type(self, index):
        if index == 0:
            return GObject.TYPE_STRING
        elif index == 1:
            return GObject.TYPE_PYOBJECT
        elif index == 2:
            return GObject.TYPE_BOOLEAN

    def do_get_iter(self, path):
        rowref = path.get_indices()[0]
        if 0 <= rowref < self._store_len:
            it = Gtk.TreeIter()
            it.user_data = rowref
            return True, it
        return False, None

    def do_get_path(self, iter_):
        return Gtk.TreePath((iter_.user_data,))

    def do_get_value(self, iter_, column):
        rowref = iter_.user_data
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

    def do_iter_next(self, iter_):
        rowref = iter_.user_data
        if rowref < self._store_len - 1:
            iter_.user_data = rowref + 1
            return True
        return False

    def do_iter_children(self, parent):
        if parent is None and self._store_len > 0:
            it = Gtk.TreeIter()
            it.user_data = 0
            return True, it
        return False, None

    def do_iter_has_child(self, iter_):
        return False

    def do_iter_n_children(self, iter_):
        if iter_ is None:
            return self._store_len
        else:
            return 0

    def do_iter_nth_child(self, parent, n):
        if parent is None and 0 <= n < self._store_len:
            it = Gtk.TreeIter()
            it.user_data = n
            return True, it
        return False, None

    def do_iter_parent(self, child):
        return False, None

    # Non-model-interface methods

    def set_editable(self, new_path):
        old_path = (self._current_editable,)
        self._current_editable = new_path[0]
        self.row_changed(old_path, self.get_iter(old_path))
        self.row_changed(new_path, self.get_iter(new_path))

    def store_index_to_path(self, store_index):
        return (store_index,)

    def path_to_store_index(self, path):
        if path is None:
            return 0
        return path[0]
