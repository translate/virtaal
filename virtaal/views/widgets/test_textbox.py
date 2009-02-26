#!/usr/bin/env python

import gtk

from textbox import *


class TextWindow(gtk.Window):
    def __init__(self, textbox=None):
        super(TextWindow, self).__init__()
        if textbox is None:
            textbox = TextBox()

        self.vbox = gtk.VBox()
        self.add(self.vbox)

        self.textbox = textbox
        self.vbox.add(textbox)

        self.connect('destroy', lambda *args: gtk.main_quit())
        self.set_size_request(400, 300)


class TestTextBox(object):
    def __init__(self):
        self.window = TextWindow()


if __name__ == '__main__':
    window = TextWindow()
    window.show_all()
    window.textbox.set_text('this <b>is</b> a test.')
    gtk.main()
