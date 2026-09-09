#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import Gtk.gdk
from gi.repository import GObject, Gtk

from virtaal.views import markup


class LabelExpander(Gtk.EventBox):
    __gproperties__ = {
        "expanded": (GObject.TYPE_BOOLEAN,
                     "expanded",
                     "A boolean indicating whether this widget has been expanded to show its contained widget",
                     False,
                     GObject.ParamFlags.READWRITE),
    }

    def __init__(self, widget, get_text, expanded=False):
        super().__init__()

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

    def do_get_property(self, prop):
        return getattr(self, prop.name)

    def do_set_property(self, prop, value):
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
            self.label.get_child().set_markup(
                markup.markuptext(self.get_text(), fancyspaces=False, markupescapes=False))

        self.get_child().show()

    expanded = property(_get_expanded, _set_expanded)
