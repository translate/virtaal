#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Manual, interactive demo for PopupWidgetButton - opens a real window
for a human to eyeball, not an automated test. Run directly:
python -m virtaal.views.widgets.demo_popupwidgetbutton"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .popupwidgetbutton import PopupWidgetButton

if __name__ == '__main__':
    btn = PopupWidgetButton(label='TestMe', widget=Gtk.Button(label='Click me'))

    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    hbox.pack_start(Gtk.Button(label='Left'), False, False, 0)
    hbox.pack_start(btn, False, False, 0)
    hbox.pack_start(Gtk.Button(label='Right'), False, False, 0)
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    vbox.pack_start(hbox, False, False, 0)

    wnd = Gtk.Window()
    wnd.set_size_request(400, 300)
    wnd.set_title('Pop-up Window Button Test')
    wnd.add(vbox)
    wnd.connect('destroy', lambda *args: Gtk.main_quit())
    wnd.show_all()
    Gtk.main()
