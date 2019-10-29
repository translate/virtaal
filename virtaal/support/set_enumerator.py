#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2009,2011 Zuza Software Foundation
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

from bisect import bisect_left

from gi.repository import GObject

from virtaal.support.sorted_set import SortedSet


# FIXME: Add docstrings!

class UnionSetEnumerator(GObject.GObject):
    __gtype_name__ = "UnionSetEnumerator"

    __gsignals__ = {
        "remove": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_INT, GObject.TYPE_PYOBJECT)),
        "add": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_INT, GObject.TYPE_PYOBJECT))
    }

    def __init__(self, *sets):
        GObject.GObject.__init__(self)

        if len(sets) > 0:
            self.sets = sets
            self.set = sets[0]
            for set_ in sets[1:]:
                # not nice, but hopefully correct for now
                self.set = self.set.union(set_)
        else:
            self.sets = [SortedSet([])]
            self.set = SortedSet([])

    #cursor = property(lambda self: self._current_element, _set_cursor)

    def __len__(self):
        return len(self.set.data)

    def __contains__(self, element):
        try:
            return element in self.set
        except IndexError:
            return False

    def _before_add(self, _src, _pos, element):
        if element not in self.set:
            self.set.add(element)
            cursor_pos = bisect_left(self.set.data, element)
            self.emit('add', self, cursor_pos, element)

    def _before_remove(self, _src, _pos, element):
        if element in self.set:
            self.set.remove(element)
            self.emit('remove', self, bisect_left(self.set.data, element), element)

    def remove(self, element):
        for set_ in self.sets:
            set_.remove(element)
