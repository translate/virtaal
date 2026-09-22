#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Manual, interactive demo for CellRendererWidget - opens a real window
for a human to eyeball, not an automated test. Run directly:
python demo_cellrendererwidget.py"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository.GObject import TYPE_PYOBJECT

from .cellrendererwidget import CellRendererWidget


class Tree(Gtk.TreeView):
    def __init__(self):
        self.store = Gtk.ListStore(str, TYPE_PYOBJECT, bool)
        super().__init__()
        self.set_model(self.store)
        self.set_headers_visible(True)

        self.append_column(Gtk.TreeViewColumn('First', Gtk.CellRendererText(), text=0))
        self.append_column(Gtk.TreeViewColumn('Second', CellRendererWidget(
            lambda widget: '<b>' + widget.get_children()[0].get_label() + '</b>'), widget=1))

    def insert(self, name):
        iter = self.store.append()
        hb = Gtk.HBox()
        hb.pack_start(Gtk.Button.new_with_label(name), False, True, 0)
        lbl = Gtk.Label(label=(name + ' ') * 20)
        lbl.set_line_wrap(True)
        hb.pack_start(lbl, False, True, 0)
        self.store.set(iter, 0, name, 1, hb, 2, True)


if __name__ == "__main__":
    w = Gtk.Window()
    w.set_position(Gtk.WindowPosition.CENTER)
    w.connect('delete-event', Gtk.main_quit)
    t = Tree()
    t.insert('foo')
    t.insert('bar')
    t.insert('baz')
    w.add(t)

    w.show_all()
    Gtk.main()
