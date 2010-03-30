#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import gtk
from gobject import SIGNAL_RUN_FIRST


class WelcomeScreen(gtk.ScrolledWindow):
    """
    The scrolled window that contains the welcome screen container widget.
    """

    __gtype_name__ = 'WelcomeScreen'
    __gsignals__ = { 'button-clicked': (SIGNAL_RUN_FIRST, None, (str,)) }


    # INITIALISERS #
    def __init__(self, gui):
        """Constructor.
            @type  gui: C{gtk.glade.XML}
            @param gui: The Glade XML object to retrieve the welcome screen from."""
        super(WelcomeScreen, self).__init__()

        self.gui = gui

        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        win = gui.get_widget('WelcomeScreen')
        if not win:
            raise ValueError('Welcome screen not found in Glade object.')
        child = win.child
        win.remove(child)
        self.add_with_viewport(child)

        self._get_widgets()
        self._init_feature_view()

    def _get_widgets(self):
        self.widgets = {}
        widget_names = ('img_banner', 'txt_features')
        for wname in widget_names:
            self.widgets[wname] = self.gui.get_widget(wname)

        self.widgets['buttons'] = {}
        button_names = (
            'open', 'recent1', 'recent2', 'recent3', 'recent4', 'recent5',
            'tutorial', 'cheatsheet', 'manual', 'locguide', 'feedback'
        )
        for bname in button_names:
            self.widgets['buttons'][bname] = self.gui.get_widget('btn_' + bname)
            self.widgets['buttons'][bname].connect('clicked', self._on_button_clicked, bname)

    def _init_feature_view(self):
        features = u"\n".join([
            u" • " + _("Extensive format support"),
            u" • " + _("Translation memory"),
            u" • " + _("Terminology assistance"),
            u" • " + _("Machine translation"),
            u" • " + _("Highlighting and insertion of placeables"),
            u" • " + _("Many plugins and options for customisation"),
        ])
        self.widgets['txt_features'].get_buffer().set_text(features)


    # METHODS #
    def set_banner_image(self, filename):
        self.widgets['img_banner'].set_from_file(filename)


    # SIGNAL HANDLERS #
    def _on_button_clicked(self, button, name):
        self.emit('button-clicked', name)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print 'Usage: %s <glade file>' % (sys.argv[0])
        exit(1)

    from gtk import glade
    gui = glade.XML(sys.argv[1])
    ws = WelcomeScreen(gui)
    window = gtk.Window()
    window.set_title('WelcomeScreen Test')
    window.connect('destroy', lambda *args: gtk.main_quit())
    window.set_size_request(400, 300)
    window.add(ws)
    window.show_all()
    gtk.main()
