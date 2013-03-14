#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Pango

from virtaal.views import markup

class LabelExpander(Gtk.EventBox):
    __gproperties__ = {
        "expanded": (GObject.TYPE_BOOLEAN,
                     "expanded",
                     "A boolean indicating whether this widget has been expanded to show its contained widget",
                     False,
                     GObject.PARAM_READWRITE),
    }

    def __init__(self, widget, get_text, expanded=False):
        super(LabelExpander, self).__init__()

        label_text = Gtk.Label()
        label_text.set_single_line_mode(False)
        label_text.set_line_wrap(True)
        label_text.set_justify(Gtk.Justification.FILL)
        label_text.set_use_markup(True)

        self.label = Gtk.EventBox()
        self.label.add(label_text)

        self.widget = widget
        self.get_text = get_text

        self.expanded = expanded

        #self.label.connect('button-release-event', lambda widget, *args: setattr(self, 'expanded', True))

    def get_property(self, prop):
        return getattr(self, prop.name)

    def set_property(self, prop, value):
        setattr(self, prop.name, value)

    def _get_expanded(self):
        return self.get_child() == self.widget

    def _set_expanded(self, value):
        if self.get_child() != None:
            self.remove(self.get_child())

        if value:
            self.add(self.widget)
        else:
            self.add(self.label)
            self.label.get_child().set_markup(markup.markuptext(self.get_text(), fancyspaces=False, markupescapes=False))

        self.get_child().show()

    expanded = property(_get_expanded, _set_expanded)
