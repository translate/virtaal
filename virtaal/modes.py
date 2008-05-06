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

from pan_app import _
from support.set_enumerator import UnionSetEnumerator
from virtaal.support.sorted_set import SortedSet

class BidiIterator(object):
    def __init__(self, itr):
        self.itr  = iter(itr)
        self.hist = []
        self.pos  = -1

    def next(self):
        if self.pos < len(self.hist) - 1:
            val = self.hist[self.pos]
            self.pos += 1
            return val
        else:
            self.hist.append(self.itr.next())
            self.pos += 1
            return self.hist[-1]

    def prev(self):
        if self.pos > -1:
            val = self.hist[self.pos]
            self.pos -= 1
            return val
        else:
            raise StopIteration()

    def __iter__(self):
        return self

class DefaultMode(UnionSetEnumerator):
    mode_name = "Default"
    user_name = _(mode_name)

    def __init__(self, stats):
        UnionSetEnumerator.__init__(self, SortedSet(stats['total']))

class QuickTranslateMode(UnionSetEnumerator):
    mode_name = "Quick Translate"
    user_name = _(mode_name)

    def __init__(self, stats):
        UnionSetEnumerator.__init__(self, SortedSet(stats['fuzzy']), SortedSet(stats['untranslated']))

MODES = dict((val.mode_name, val) for val in pan_app().itervalues() if hasattr(val, 'mode_name'))


