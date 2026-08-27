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

"""Manual, interactive demo for TextBox - opens a real window for a human
to eyeball, not an automated test. Run directly: python demo_textbox.py
(Renamed from test_textbox.py, which pytest was picking up by filename
convention alone despite having no assertions.)"""

from gi.repository import Gtk

from .textbox import TextBox


class TextWindow(Gtk.Window):
    def __init__(self, textbox=None):
        super().__init__()
        if textbox is None:
            textbox = TextBox(self)

        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        self.textbox = textbox
        self.vbox.add(textbox)

        self.connect('destroy', lambda *args: Gtk.main_quit())
        self.set_size_request(600, 100)

class TestTextBox(object):
    def __init__(self):
        self.window = TextWindow()


if __name__ == '__main__':
    window = TextWindow()
    window.show_all()
    window.textbox.set_text(u'Ģët <a href="http://www.example.com" alt="Ģët &brand;!">&brandLong;</a>')
    Gtk.main()
