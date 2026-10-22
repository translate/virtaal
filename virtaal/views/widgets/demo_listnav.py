#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Manual, interactive demo for ListNavigator - opens a real window for a
human to eyeball, not an automated test. Run directly:
python -m virtaal.views.widgets.demo_listnav"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .listnav import ListNavigator


class _Item:
    def __init__(self, i):
        self.i = i

    def __str__(self):
        return '<Item i=%s>' % (self.i)


def _create_model():
    model = Gtk.ListStore(str, object)
    for i in range(10):
        model.append([str(i), _Item(i)])
    return model


if __name__ == '__main__':
    # Uncomment below to test RTL
    #Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
    listnav = ListNavigator()

    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    hbox.pack_start(listnav, False, False, 0)
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    vbox.pack_start(hbox, False, False, 0)

    wnd = Gtk.Window()
    wnd.set_title('List Navigator Test')
    wnd.set_size_request(400, 300)
    wnd.add(vbox)
    wnd.connect('destroy', lambda *args: Gtk.main_quit())
    listnav.set_parent_window(wnd)

    def on_selection_changed(sender, selected):
        sender.btn_popup.set_label('Item %d' % (selected.i))
    listnav.connect('selection-changed', on_selection_changed)
    listnav.set_model(_create_model())

    wnd.show_all()
    Gtk.main()
