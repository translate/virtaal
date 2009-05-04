#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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
from translate.storage.placeables import base, StringElem


class StringElemGUI(object):
    """
    A convenient container for all GUI properties of a L{StringElem}.
    """

    # MEMBERS #
    fg = '#000000'
    """The current foreground colour."""
    bg = '#ffffff'
    """The current background colour."""

    child_offsets = {}
    """Offsets of child strings in the "rendered" string."""
    cursor_allowed = True
    """Whether the cursor is allowed to enter this element."""


    # INITIALIZERS #
    def __init__(self, elem, textbox, **kwargs):
        if not isinstance(elem, StringElem):
            raise ValueError('"elem" parameter must be a StringElem.')
        self.child_offsets = {}
        self.elem = elem
        self.textbox = textbox
        self.marks = {}

        attribs = ('fg', 'bg', 'cursor_allowed')
        for kw in kwargs:
            if kw in attribs:
                setattr(self, kw, kwargs[kw])

    # METHODS #
    def create_tags(self):
        tag = gtk.TextTag()
        if self.fg:
            tag.props.foreground = self.fg

        if self.bg:
            tag.props.background = self.bg

        return [(tag, None, None)]

    def create_widget(self):
        return None

    def copy(self):
        return self.__class__(
            elem=self.elem, textbox=self.textbox,
            fg=self.fg, bg=self.bg,
            cursor_allowed=self.cursor_allowed
        )

    def elem_at_offset(self, offset):
        """Find the C{StringElem} at the given offset.
            This method is used in Virtaal as a replacement for
            C{StringElem.elem_at_offset}, because this method takes the
            transformations by L{render}() into account."""
        sorted_offsets = self.child_offsets.items()
        sorted_offsets.sort(lambda a, b: cmp(a[1], b[1]))
        if offset < sorted_offsets[0][1]:
            return sorted_offsets[0][0]
        for i in range(len(sorted_offsets)-1):
            if sorted_offsets[i][1] <= offset < sorted_offsets[i+1][1]:
                return sorted_offsets[i][0]
        return sorted_offsets[-1][0]

    def get_prefix(self):
        return ''

    def get_postfix(self):
        return ''

    def index(self, elem):
        """Replacement for C{StringElem.elem_offset()} to be aware of the
            changes made by L{render()}."""
        if not isinstance(elem, StringElem) and self.elem.isleaf():
            return 0
        if elem is self.elem:
            return 0
        for e in self.elem.sub:
            if e is elem and e in self.child_offsets:
                return self.child_offsets[elem]
            if hasattr(e, 'gui_info'):
                idx = e.gui_info.index(elem)
                if idx >= 0:
                    return self.child_offsets[e] + idx
        return -1

    def render(self, elem):
        assert elem is self.elem
        childstr = u''
        prefixoffset = len(self.get_prefix())
        offset = 0
        for sub in self.elem.sub:
            key = sub
            if not isinstance(sub, StringElem):
                key = self.elem
            self.child_offsets[key] = prefixoffset + len(childstr)
            childstr += unicode(sub)
        return u'%s%s%s' % (self.get_prefix(), childstr, self.get_postfix())


class PhGUI(StringElemGUI):
    fg = 'darkred'
    bg = '#f7f7f7'


class GPlaceableGUI(StringElemGUI):
    fg = '#f7f7f7'
    bg = 'darkred'

    def create_tags(self):
        metatag = gtk.TextTag()
        metatag.props.foreground = self.fg
        metatag.props.background = self.bg

        ttag = gtk.TextTag()
        ttag.props.foreground = StringElemGUI.fg
        ttag.props.background = 'yellow'

        prefixlen = len(self.get_prefix())
        return [
            (metatag, 0, -1),
            (ttag, prefixlen, -2),
        ]

    def get_prefix(self):
        return u'%s{' % (self.elem.id)

    def get_postfix(self):
        return u'}'

class XPlaceableGUI(StringElemGUI):
    fg = '#ffffff'
    bg = '#000000'

    def get_prefix(self):
        return u'{%s' % (self.elem.id)

    def get_postfix(self):
        return u'}'


element_gui_map = [
    (base.Ph, PhGUI),
    (base.G, GPlaceableGUI),
    (base.X, XPlaceableGUI),
]
