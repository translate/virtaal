#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007 Zuza Software Foundation
#
# This file is part of virtaal.
#
# translate is free software; you can redistribute it and/or modify
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
from virtaal.support.sorted_set import SortedSet

import gobject

class UnionSetEnumerator(gobject.GObject):
    __gtype_name__ = "UnionSetEnumerator"

    __gsignals__ = {}

    def __init__(self, *sets):
        gobject.GObject.__init__(self)

        if len(sets) > 0:
            self.sets = sets
            self.set = reduce(lambda big_set, set: big_set.union(set), sets[1:], sets[0])
            for set in self.sets:
                set.connect('before-add', self._before_add)
                set.connect('before-remove', self._before_remove)
        else:
            self.sets = [SortedSet([])]
            self.set = SortedSet([])

        self._item_to_cursor_map = dict((item, index) for index, item in enumerate(self))
        self._cursor = -1

    def _set_cursor(self, value):
        if 0 <= value < len(self.set.data):
            self._current_index = value
        else:
            raise IndexError()

    cursor = property(lambda self: self._current_index, _set_cursor)

    def _in_set(self, item):
        try:
            return self.set.data[bisect_left(self.set.data, item)] == item
        except IndexError:
            return False

    def _before_add(self, src, pos, item):
        if not self._in_set(item):
            self.set.add(item)
            add_index = bisect_left(self.set.data, item)
            self._item_to_cursor_map[item] = add_index
            if self._current_index >= add_index:
                self._current_index += 1

    def _before_remove(self, src, pos, item):
        if self._in_set(item):
            self.set.remove(item)
            del self._item_to_cursor_map[item]
            if self._current_index >= bisect_left(self.set.data, item):
                self._current_index -= 1

    def __iter__(self):
        def iterator():
            for item in self.set.data:
                yield item

        return iterator()

    def get_cursor(self, item):
        return self._item_to_cursor_map[item]

    def __getitem__(self, cursor):
        return self.set.data[self.cursor]

    def remove(self, item):
        for set in self.sets:
            set.remove(item)

