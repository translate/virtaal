#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from bisect import bisect_left

from gi.repository import GObject, Gtk

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
    its integer row number, stored directly in Gtk.TreeIter.user_data.

    The rows are every unit in the store, or only those at the store
    indices given as C{rows}; row numbers and store indices then differ.
    """

    def __init__(self, storemodel, rows=None):
        super().__init__()
        self._store = storemodel
        self._store_len = len(storemodel)
        self._rows = None
        self._row_of = None
        if rows is not None:
            self._rows = list(rows)
        # A store index, so it survives rows being shown and hidden.
        self._current_editable = 0

    @property
    def visible_rows(self):
        """The store indices shown, or C{None} for every unit."""
        return self._rows

    def row_count(self):
        return self._store_len if self._rows is None else len(self._rows)

    def unit_at_row(self, row):
        return self._store[self._store_index(row)]

    def _store_index(self, row):
        return row if self._rows is None else self._rows[row]

    def _row(self, store_index):
        if self._rows is None:
            return store_index if 0 <= store_index < self._store_len else None
        if self._row_of is None:
            self._row_of = {index: row for row, index in enumerate(self._rows)}
        return self._row_of.get(store_index)

    def _iter(self, row):
        it = Gtk.TreeIter()
        it.user_data = row
        return it

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
        row = path.get_indices()[0]
        if 0 <= row < self.row_count():
            return True, self._iter(row)
        return False, None

    def do_get_path(self, iter_):
        return Gtk.TreePath((iter_.user_data,))

    def do_get_value(self, iter_, column):
        index = self._store_index(iter_.user_data)
        if column <= 1:
            unit = self._store[index]
            if column == 0:
                note_text = unit.getnotes()
                if not note_text:
                    locations = unit.getlocations()
                    if locations:
                        note_text = locations[0]
                return markup.markuptext(note_text, fancyspaces=False, markupescapes=False)
            else:
                return unit
        else:
            return self._current_editable == index

    def do_iter_next(self, iter_):
        row = iter_.user_data
        if row < self.row_count() - 1:
            iter_.user_data = row + 1
            return True
        return False

    def do_iter_children(self, parent):
        if parent is None and self.row_count() > 0:
            return True, self._iter(0)
        return False, None

    def do_iter_has_child(self, iter_):
        return False

    def do_iter_n_children(self, iter_):
        if iter_ is None:
            return self.row_count()
        else:
            return 0

    def do_iter_nth_child(self, parent, n):
        if parent is None and 0 <= n < self.row_count():
            return True, self._iter(n)
        return False, None

    def do_iter_parent(self, child):
        return False, None

    # Non-model-interface methods

    def set_visible_rows(self, rows):
        """Show only the units at the sorted store indices C{rows}, or every
            unit for C{None}, emitting row-deleted/row-inserted for the
            rows that change."""
        current = list(range(self._store_len)) if self._rows is None else self._rows
        wanted = list(range(self._store_len)) if rows is None else list(rows)
        old_last = current[-1] if current else None
        wanted_set = set(wanted)
        self._rows = current
        # Deleted from the end, so the row numbers still to delete stay valid.
        for row in range(len(current) - 1, -1, -1):
            if current[row] not in wanted_set:
                del current[row]
                self._row_of = None
                self.row_deleted(Gtk.TreePath((row,)))
        current_set = set(current)
        for index in wanted:
            if index not in current_set:
                row = bisect_left(current, index)
                current.insert(row, index)
                self._row_of = None
                path = Gtk.TreePath((row,))
                self.row_inserted(path, self._iter(row))
        if rows is None:
            self._rows = None
            self._row_of = None
        # The last row is padded (see StoreCellRenderer.do_get_size()), so
        # both the old and the new last row need measuring again.
        new_last = self._store_index(self.row_count() - 1) if self.row_count() else None
        if new_last != old_last:
            for index in (old_last, new_last):
                row = None if index is None else self._row(index)
                if row is not None:
                    self.row_changed(Gtk.TreePath((row,)), self._iter(row))

    def set_editable(self, new_path):
        old_row = self._row(self._current_editable)
        self._current_editable = self.path_to_store_index(new_path)
        if old_row is not None:
            self.row_changed((old_row,), self.get_iter((old_row,)))
        self.row_changed(new_path, self.get_iter(new_path))

    def store_index_to_path(self, store_index):
        """The path of the unit at C{store_index}, or C{None} if it isn't shown."""
        row = self._row(store_index)
        return None if row is None else (row,)

    def path_to_store_index(self, path):
        if path is None:
            return 0
        return self._store_index(path[0])
