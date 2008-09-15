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

from virtaal.support.set_enumerator import UnionSetEnumerator
from virtaal.support.sorted_set import SortedSet
from virtaal.search_mode import SearchMode

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
    user_name = _("All")
    widgets = []

    def __init__(self):
        UnionSetEnumerator.__init__(self)

    def handle_unit(self, editor):
        """This mode has nothing to do with selected units."""
        pass

    def refresh(self, document):
        UnionSetEnumerator.__init__(self, SortedSet(document.stats['total']))

    def selected(self):
        """There is nothing to do after this mode has been selected, so this
            method does exactly that: nothing."""
        pass

class QuickTranslateMode(UnionSetEnumerator):
    mode_name = "Quick Translate"
    user_name = _("Incomplete")
    widgets = []

    def __init__(self):
        UnionSetEnumerator.__init__(self)

    def handle_unit(self, editor):
        """This mode has nothing to do with selected units."""
        pass

    def refresh(self, document):
        UnionSetEnumerator.__init__(self, SortedSet(document.stats['fuzzy']), SortedSet(document.stats['untranslated']))

    def selected(self):
        """There is nothing to do after this mode has been selected, so this
            method does exactly that: nothing."""
        pass


MODES = dict( (klass.mode_name, klass()) for klass in globals().itervalues() if hasattr(klass, 'mode_name') )
