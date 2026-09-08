#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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

class TestTextBox:
    def __init__(self):
        self.window = TextWindow()


if __name__ == '__main__':
    window = TextWindow()
    window.show_all()
    window.textbox.set_text('Ģët <a href="http://www.example.com" alt="Ģët &brand;!">&brandLong;</a>')
    Gtk.main()
