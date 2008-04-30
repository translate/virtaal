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

class DefaultMode(object):
    def __init__(self, units):
        self._units = units
        self._remap = xrange(len(units))

    def _is_valid(self, index):
        return self._units[index].istranslatable()

    def __iter__(self):
        return (i for i in self._remap if self._is_valid(i))

class QuickTranslateMode(DefaultMode):
    def __init__(self, units):
        super(QuickTranslateMode, self).__init__(units)

    def _is_valid(self, index):
        return super(QuickTranslateMode, self)._is_valid and \
               (not self._units[index].istranslated() or self._units[index].isfuzzy())

    